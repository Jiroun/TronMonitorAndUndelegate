import time
from datetime import datetime
import pytz
import requests

class TronEnergyMonitor:
    def __init__(self, telegram_token, chat_id):
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.wallets = []  # List of {"address": ..., "notified": False}

    def add_wallet(self, address):
        self.wallets.append({
            "address": address,
            "notified_energy_ready": False  # for available energy alert
        })

    def get_to_accounts(self, address):
        url = "https://api.trongrid.io/wallet/getdelegatedresourceaccountindexv2"
        data = {"value": address, "visible": True}
        response = requests.post(url, json=data)
        return response.json().get("toAccounts", [])

    def get_delegation_details(self, from_address, to_address):
        url = "https://api.trongrid.io/wallet/getdelegatedresourcev2"
        data = {
            "fromAddress": from_address,
            "toAddress": to_address,
            "visible": True
        }
        response = requests.post(url, json=data)
        return response.json().get("delegatedResource", [])

    def get_energy_status(self, wallet_address):
        try:
            url = f"https://apilist.tronscan.org/api/account?address={wallet_address}"
            response = requests.get(url)
            data = response.json()
            energy = data.get('bandwidth', {})
            remaining = int(energy.get('energyRemaining', 0))
            limit = int(energy.get('energyLimit', 0))
            return remaining, limit
        except Exception as e:
            print(f"[ERROR] Getting energy info failed: {e}")
            return 0, 1  # avoid division by zero

    def send_telegram(self, message, silent=True):
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "disable_notification": silent
        }
        try:
            requests.post(url, params=payload)
        except Exception as e:
            print(f"[ERROR] Telegram message failed: {e}")

    def check_expired_delegations(self):
        now_ms = int(datetime.now(pytz.utc).timestamp() * 1000)
        for wallet in self.wallets:
            address = wallet["address"]
            print(f"\n🔍 Checking wallet: {address}")
            to_accounts = self.get_to_accounts(address)

            for to in to_accounts:
                delegations = self.get_delegation_details(address, to)
                for entry in delegations:
                    expire_time = entry.get("expire_time_for_energy", 0)
                    if expire_time < now_ms:
                        expire_dt = datetime.fromtimestamp(expire_time / 1000, pytz.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
                        msg = (
                            f"⚠️ Expired Energy Delegation!\n"
                            f"Delegated from: {address}\n"
                            f"To: {to}\n"
                            f"Expired at: {expire_dt}\n"
                            f"يرجى فك التفويض يدوياً."
                        )
                        self.send_telegram(msg, silent=True)
                        print(msg)

    def check_energy_availability(self):
        for wallet in self.wallets:
            address = wallet["address"]
            remaining, limit = self.get_energy_status(address)
            if limit == 0:
                continue

            ratio = remaining / limit
            is_available = ratio >= 0.95

            if is_available and not wallet["notified_energy_ready"]:
                msg = f"🟢 Energy is now available to delegate!\nWallet: {address}\nAvailable: {remaining}/{limit} ({ratio:.2%})"
                self.send_telegram(msg, silent=False)  # LOUD alert
                wallet["notified_energy_ready"] = True
                print(msg)
            elif not is_available:
                wallet["notified_energy_ready"] = False

    def run(self, interval_seconds=600):
        print("🚀 Starting Tron Energy Monitor...")
        while True:
            try:
                self.check_expired_delegations()
                self.check_energy_availability()
            except Exception as e:
                print(f"[ERROR] Main loop failed: {e}")
            time.sleep(interval_seconds)

# === Example usage ===
if __name__ == "__main__":
    TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
    CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"

    monitor = TronEnergyMonitor(TELEGRAM_TOKEN, CHAT_ID)

    # Example wallet (replace with your real data)
    monitor.add_wallet("TPx3ehU7mictyZX7sv4YU4eXfuwm888888")

    monitor.run()
