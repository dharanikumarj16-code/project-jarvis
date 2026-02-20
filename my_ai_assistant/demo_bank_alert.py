from datetime import datetime
def show_professional_alert():
    # Get current timestamp
    now = datetime.now()
    date_str = now.strftime("%d-%b-%Y")
    time_str = now.strftime("%H:%M EST")

    # Professional Bank Alert Template
    message = (
        f"Canada Bank ALERT: CAD 1,500.00 has been debited from A/c XXXX2457 "
        f"on {date_str} at {time_str}.\n"
        f"Txn Ref: POS Purchase – Montreal.\n"
        f"Available Balance: CAD 567.90\n"
        f"- Canada Bank"
    )
    print(message)
if __name__ == "__main__":
    show_professional_alert()
