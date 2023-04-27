import asyncio
import hashlib
import hmac
import json
import logging
import telegram
import time
import typing

import aiohttp
import aiostream
import websockets
import argparse

logging.basicConfig(
    level=logging.INFO
)

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


async def position(network: typing.Literal['mainnet', 'testnet'], api_public_key: str, api_secret_key: str):
    timestamp = str(int(time.time() * 1000))

    async with aiohttp.ClientSession() as session:
        response = await session.get(
            f"{ENDPOINTS[network]['HTTP']}/v1/positions",
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


async def fills(network: typing.Literal['mainnet', 'testnet'], application_id: str, api_public_key: str, api_secret_key: str):
    async for connection in websockets.connect(ENDPOINTS[network]['WS_PUBLIC'].format(application_id=application_id)):
        try:
            timestamp = str(int(time.time() * 1000))

            await connection.send(json.dumps({
                'id': 'test',
                'event': 'auth',
                'params': {
                    'apikey': api_public_key,
                    'sign': signature(timestamp, api_secret_key),
                    'timestamp': timestamp
                }
            }))

            await connection.send(json.dumps({
                "id": "test",
                "topic": "executionreport",
                "event": "subscribe"
            }))

            async def ping():
                await connection.send(json.dumps({'event': 'ping'}))

            async for raw_message in connection:
                message = json.loads(raw_message)

                if message.get('event') == 'ping': asyncio.ensure_future(ping())

                if 'data' not in message:
                    continue

                yield message
        except Exception as exception:
            logging.error(exception)


async def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--network',
        choices=['mainnet', 'testnet'],
        default='mainnet'
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
        '--telegram',
        type=str
    )

    args = parser.parse_args()

    print(await position(
        network=args.network,
        api_public_key=args.api_public_key,
        api_secret_key=args.api_secret_key
    ))

    async with aiostream.stream.merge(
        fills(args.network, args.application_id, args.api_public_key, args.api_secret_key)
    ).stream() as streamer:
        async for message in streamer:
            print(message)

if __name__ == '__main__':
    asyncio.run(main())
