import argparse
import asyncio
import contextlib
import hashlib
import hmac
import json
import logging
import sys
import time
import typing

import aiohttp
import aiostream
import telegram
import websockets
import secrets

ENDPOINTS = {
    'mainnet': {
        'HTTP': 'https://api.woo.org',
        'WS_PUBLIC': 'wss://wss.woo.org/ws/stream/{application_id}',
        'WS_PRIVATE': 'wss://wss.woo.org/v2/ws/private/stream/{application_id}',
    },
    'testnet': {
        'HTTP': 'https://api.staging.woo.org',
        'WS_PUBLIC': 'wss://wss.staging.woo.org/ws/stream/{application_id}',
        'WS_PRIVATE': 'wss://wss.staging.woo.org/v2/ws/private/stream/{application_id}',
    },
}


def signature(timestamp: str, api_key_secret: str, **kwargs):
    msg = ""

    args = {key: value for key, value in sorted(kwargs.items())}

    for key, value in args.items():
        if msg:
            msg += "&"
        msg += f"{key}={value}"
    msg += f"|{timestamp}"

    key = bytes(str(api_key_secret), "utf-8")

    msg = bytes(msg, "utf-8")

    return (
        hmac.new(key, msg=msg, digestmod=hashlib.sha256)
            .hexdigest()
            .upper()
    )


async def public_request(network: typing.Literal['mainnet', 'testnet'], endpoint: str):
    async with aiohttp.ClientSession() as session:
        response = await session.get(f"{ENDPOINTS[network]['HTTP']}{endpoint}")

        try:
            content = await response.json()

            response.raise_for_status()

            return content
        except Exception as exception:
            logging.error(content or exception)

async def private_request(network: typing.Literal['mainnet', 'testnet'], api_public_key: str, api_secret_key: str, endpoint: str):
    timestamp = str(int(time.time() * 1000))

    async with aiohttp.ClientSession() as session:
        response = await session.get(
            f"{ENDPOINTS[network]['HTTP']}{endpoint}",
            headers={
                'x-api-key': api_public_key,
                'x-api-signature': signature(timestamp, api_secret_key),
                'x-api-timestamp': timestamp
            }
        )

        try:
            content = await response.json()

            response.raise_for_status()

            return content
        except Exception as exception:
            logging.error(content or exception)


async def private_stream(network: typing.Literal['mainnet', 'testnet'], application_id: str, api_public_key: str, api_secret_key: str, topic: str):
    async for connection in websockets.connect(ENDPOINTS[network]['WS_PRIVATE'].format(application_id=application_id)):
        try:
            timestamp = str(int(time.time() * 1000))

            tag = secrets.token_urlsafe(8)

            await connection.send(json.dumps({
                'id': tag,
                'event': 'auth',
                'params': {
                    'apikey': api_public_key,
                    'sign': signature(timestamp, api_secret_key),
                    'timestamp': timestamp
                }
            }))

            await connection.send(json.dumps({
                "id": tag,
                "topic": topic,
                "event": "subscribe"
            }))

            async def ping():
                await connection.send(json.dumps({'event': 'ping'}))

            async for raw_message in connection:
                message = json.loads(raw_message)

                if message.get('event') == 'ping': asyncio.ensure_future(ping())

                if 'data' not in message:
                    continue

                yield topic, message
        except Exception as exception:
            logging.error(exception)


async def main():
    parser = argparse.ArgumentParser(
        prog='woostream',
        description='Stream fills & position updates from Woo X'
    )

    parser.add_argument(
        '--network',
        choices=['mainnet', 'testnet'],
        default='mainnet',
        help='mainnet uses x.staging.woo.org, whilst testnet x.woo.org'
    )

    parser.add_argument(
        '--application-id',
        type=str,
        required=True
    )

    parser.add_argument(
        '--api-public-key',
        type=str,
        required=True
    )

    parser.add_argument(
        '--api-secret-key',
        type=str,
        required=True
    )

    parser.add_argument(
        '--telegram-token',
        type=str,
        required='--telegram-chat-id' in sys.argv
    )

    parser.add_argument(
        '--telegram-chat-id',
        type=str,
        required='--telegram-token' in sys.argv
    )

    parser.add_argument(
        '--log-level',
        type=str,
        choices=list(logging._nameToLevel.keys()),
        default=logging._levelToName[logging.INFO]
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging._nameToLevel[args.log_level]
    )

    async with (
        aiostream.stream.merge(
            private_stream(args.network, args.application_id, args.api_public_key, args.api_secret_key, 'position'),
            private_stream(args.network, args.application_id, args.api_public_key, args.api_secret_key, 'executionreport')
        ).stream() as streamer,
        telegram.Bot(args.telegram_token) if args.telegram_token else contextlib.nullcontext() as bot
    ):
        async def broadcast(message: str):
            print(message)

            if bot:
                await bot.send_message(
                    text=message,
                    chat_id=args.telegram_chat_id
                )

        tokens = await public_request(args.network, '/v1/public/info')

        positions, balances = await asyncio.gather(*[
            private_request(
                network=args.network,
                api_public_key=args.api_public_key,
                api_secret_key=args.api_secret_key,
                endpoint='/v1/positions'
            ),
            private_request(
                network=args.network,
                api_public_key=args.api_public_key,
                api_secret_key=args.api_secret_key,
                endpoint='/v1/client/holding'
            ),
        ])

        asyncio.ensure_future(broadcast("\n".join([
            f"Positions:",
            *[
                f"- {position['symbol']}: {position['holding']} @ {position['average_open_price']}"
                for position in positions.get('positions', [])
                if position['holding'] != 0
            ],
            f"Balances:",
            *[
                f"- {asset}: {round(holding, str(meta['base_tick']).count('0')) if meta['base_tick'] < 1 else holding}"
                for asset, holding, meta in [
                    [asset, holding, [
                        entry for entry in tokens['rows']
                        if entry['symbol'] == f"SPOT_{asset}_USDT" or (asset == 'USDT' and entry['symbol'] == 'SPOT_USDC_USDT')
                    ][0]]
                    for asset, holding in balances.get('holding', {}).items()
                ]
                if holding > meta['base_tick']
            ],
        ])))

        async for topic, message in streamer:
            match topic:
                case 'position':
                    pass
                case 'executionreport':
                    if message['data']['status'] == 'FILLED':
                        asyncio.ensure_future(broadcast("\n".join([
                            f"{'Bought' if message['data']['side'] == 'BUY' else 'Sold'} {message['data']['totalExecutedQuantity']} {message['data']['symbol']} @ {message['data']['avgPrice']}"
                        ])))

if __name__ == '__main__':
    asyncio.run(main())
