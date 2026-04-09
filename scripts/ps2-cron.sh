#!/bin/bash
# PS2 Auction Monitor - OpenClaw Cron Job
# Searches eBay Italy for PS2 game auctions and sends results to Telegram

EBAY_URL="https://www.ebay.it/sch/139973/i.html?_nkw=PS2+videogiochi+asta&_sacat=139973&LH_AUCTION=1&_udhi=20"

# Log check
echo "[PS2 Monitor] Checking auctions at $(date)"

# This script is triggered by OpenClaw cron
# The actual search logic will be handled by an OpenClaw agent message

echo "OK"
