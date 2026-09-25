"""
Ledger & Vault -- demo banking backend.

In-memory data only: everything resets when the server restarts.
This is a teaching/demo backend, not production banking software --
there's no authentication, encryption, or persistence layer.

Run:
    pip install -r requirements.txt
    python app.py

Then open http://localhost:5000 in a browser.
"""

import itertools
import threading
import time

from flask import Flask, jsonify, request, render_template, abort

app = Flask(__name__)

# ---------------------------------------------------------------------------
# In-memory "database"
# ---------------------------------------------------------------------------
lock = threading.Lock()
accounts = {}       # id -> {id, name, balance, created}
transactions = []   # list of {id, from, to, amount, note, ts}
_id_counter = itertools.count(1001)
_tx_counter = itertools.count(1)


def new_account_id():
    return "AC-" + str(next(_id_counter))


def new_tx_id():
    return "TX-" + str(next(_tx_counter))


def seed():
    a = new_account_id()
    b = new_account_id()
    accounts[a] = {"id": a, "name": "Amara Okafor", "balance": 1250.00, "created": time.time()}
    accounts[b] = {"id": b, "name": "Tunde Bello", "balance": 480.50, "created": time.time()}


seed()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def round2(n):
    return round(float(n) + 1e-9, 2)


def account_or_404(account_id):
    acct = accounts.get(account_id)
    if not acct:
        abort(404, description="No account found with that ID.")
    return acct


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Admin API
# ---------------------------------------------------------------------------
@app.get("/api/accounts")
def list_accounts():
    with lock:
        ordered = sorted(accounts.values(), key=lambda a: a["created"])
        return jsonify(ordered)


@app.post("/api/accounts")
def create_account():
    body = request.get_json(force=True, silent=True) or {}
    name = (body.get("name") or "").strip()
    balance = body.get("balance", 0)

    if not name:
        return jsonify({"error": "Name is required."}), 400
    try:
        balance = round2(balance)
        if balance < 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "Opening balance must be a non-negative number."}), 400

    with lock:
        acct_id = new_account_id()
        accounts[acct_id] = {
            "id": acct_id,
            "name": name,
            "balance": balance,
            "created": time.time(),
        }
        return jsonify(accounts[acct_id]), 201


@app.get("/api/accounts/<account_id>")
def get_account(account_id):
    with lock:
        acct = account_or_404(account_id)
        return jsonify(acct)


@app.put("/api/accounts/<account_id>/balance")
def set_balance(account_id):
    body = request.get_json(force=True, silent=True) or {}
    try:
        balance = round2(body.get("balance"))
        if balance < 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "Balance must be a non-negative number."}), 400

    with lock:
        acct = account_or_404(account_id)
        acct["balance"] = balance
        return jsonify(acct)


@app.delete("/api/accounts/<account_id>")
def delete_account(account_id):
    with lock:
        account_or_404(account_id)
        del accounts[account_id]
        return jsonify({"deleted": account_id})


@app.get("/api/transactions")
def all_transactions():
    with lock:
        return jsonify(sorted(transactions, key=lambda t: t["ts"], reverse=True))


# ---------------------------------------------------------------------------
# Customer API
# ---------------------------------------------------------------------------
@app.get("/api/accounts/<account_id>/transactions")
def account_transactions(account_id):
    with lock:
        account_or_404(account_id)
        rows = [t for t in transactions if t["from"] == account_id or t["to"] == account_id]
        return jsonify(sorted(rows, key=lambda t: t["ts"], reverse=True))


@app.post("/api/transfer")
def transfer():
    body = request.get_json(force=True, silent=True) or {}
    from_id = (body.get("from_id") or "").strip().upper()
    to_id = (body.get("to_id") or "").strip().upper()
    note = (body.get("note") or "").strip()

    try:
        amount = round2(body.get("amount"))
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "Enter a valid transfer amount."}), 400

    if from_id == to_id:
        return jsonify({"error": "You can't transfer to your own account."}), 400

    with lock:
        sender = account_or_404(from_id)
        recipient = account_or_404(to_id)

        if amount > sender["balance"]:
            return jsonify({"error": "Insufficient balance for this transfer."}), 400

        sender["balance"] = round2(sender["balance"] - amount)
        recipient["balance"] = round2(recipient["balance"] + amount)

        tx = {
            "id": new_tx_id(),
            "from": from_id,
            "to": to_id,
            "amount": amount,
            "note": note,
            "ts": time.time(),
        }
        transactions.append(tx)
        return jsonify(tx), 201


@app.errorhandler(404)
def handle_404(e):
    return jsonify({"error": str(e.description)}), 404


if __name__ == "__main__":
    app.run(debug=False, port=5000)
