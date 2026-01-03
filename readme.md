# BlinX Discord Economy Bot

A powerful Discord economy bot with BlinX platform integration, featuring cash economy, private voice channels, auto-moderation, and real-time user/community lookups.

## 🚀 Features

### 💰 Economy System
- Daily cash rewards (`/daily`)
- Work to earn cash (`/work`)
- Withdraw cash to Blinks (`/withdraw`)
- Leaderboard rankings (`/leaderboard`)
- Admin cash management (`/addcash`, `/removecash`)

### 🎙️ Private Voice Channels
- Create private voice rooms (`/create_pr`)
- Flexible pricing based on user limits
- Transfer ownership (`/transfer_pr`)
- Delete channels (`/delete_pr`)

### 🔗 BlinX Integration
- User profile lookup (`/blinx_check`)
- Community information (`/check_blinx_community`)
- System status monitoring (`/blinx_status`)

### 🛡️ Auto-Moderation
- Blacklisted word filtering
- Comprehensive logging system
- Real-time event tracking

## ⚙️ Installation

### Prerequisites
- Python 3.8+
- Discord Bot Token
- Discord Developer Portal access

### Setup
1. Clone the repository
2. Install dependencies:
```bash
pip install disnake aiosqlite aiohttp python-dotenv