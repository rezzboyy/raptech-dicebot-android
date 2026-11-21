# Raptech Terminal Bot

Multi-site crypto dice automation bot.

## Supported Sites

- betfury
- dogepick
- faucetpay
- jacksclub
- nuts
- paradice
- pasino
- stake
- testmode (local simulator)
- tronpick
- wolfbet

## Install

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Interactive menu
python bot.py

# Non-interactive
python bot.py --site wolfbet --token YOUR_TOKEN --strategy sample.lua --currency DOGE

# Test mode (no real funds)
python bot.py --site testmode --strategy sample.lua --currency BTC --max-bets 100 --non-interactive

# List strategies
python bot.py --list-strategies

# Check script
python bot.py --check-script sample.lua
```

## Strategies

Lua strategy files go in the `strategies/` folder.

## Docs

- [docs/DISTRIBUSI.md](docs/DISTRIBUSI.md) Ã¢â‚¬â€ workflow distribusi & lisensi (admin/seller).

## Options

```
--site          Target site
--token         Web API bearer token
--currency      Currency (DOGE, BTC, TRX, etc)
--strategy      Lua strategy filename
--max-bets      Stop after N cycles (0=unlimited)
--interval-ms   Delay between cycles in ms
--take-profit-pct  Stop at profit %
--pause-on-win  Stop after a win
--quiet         Reduce output
--no-color      Disable colors
--non-interactive  Run without menu
```
