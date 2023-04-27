# woostream

Stream fills & position updates from Woo X.

## Installation

![PyPI](https://img.shields.io/pypi/v/woostream)

`woostream` is available as a [Python package on PyPI](https://pypi.org/project/woostream) and can be installed as:

```
pip install woostream
```

## How to run

`woostream` is executable as a command line utility:

```shell
# Example command, outputting to the shell
python -m woostream \
  --network testnet \
  --application-id 6a9b8f2b-3969-4c96-b127-b6649b7d976d \
  --api-public-key r0Ln7xEfpO/lEubPuEE7ug== \
  --api-secret-key XTXL4TUAN6WLCPLXAIYNYTL2MPLP 
```

Learn how to get `application-id`, `api-public-key` and `api-secret-key` [here](https://support.woo.org/hc/en-001/articles/4410291152793--How-do-I-create-the-API-).

`network` can be either `mainnet` or `testnet`; the former points to [x.woo.org](x.woo.org), whilst the latter to [x.staging.woo.org](x.staging.woo.org).

### Telegram forwarding

It's possible to output to a Telegram channel in addition to the shell, by specifying `telegram-token` and `telegram-chat-id`.

Learn how to get a `telegram-token` [here](https://core.telegram.org/bots/tutorial#obtain-your-bot-token).

You can get a `telegram-chat-id` by logging into [web.telegram.org/k](https://web.telegram.org/k), selecting a group chat you control and fetching the chat ID from the URL bar:

<img width="438" alt="Screen Shot 2023-04-27 at 13 29 58" src="https://user-images.githubusercontent.com/28162761/234878545-41b2fd1d-eba4-4dcc-9c99-33e4508ba250.png">

*Here the chat ID is -855125383.*

Then replace the command-line arguments accordingly:

```shell
python -m woostream
  --network testnet \
  --application-id 6a9b8f2b-3969-4c96-b127-b6649b7d976d \
  --api-public-key r0Ln7xEfpO/lEubPuEE7ug== \
  --api-secret-key XTXL4TUAN6WLCPLXAIYNYTL2MPLP \
  --telegram-token [TELEGRAM_TOKEN] \
  --telegram-chat-id [TELEGRAM_CHAT_ID]
```

Note that that Telegram's API has a rate limit of 30 messages per second - in any case, messages will continue to be broadcasted to the shell.
