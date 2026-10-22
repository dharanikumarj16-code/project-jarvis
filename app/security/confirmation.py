def request_confirmation(action: str, details: str) -> bool:
    print(f"\n[JARVIS SAFETY BOUNDARY] Action requires confirmation: {action}")
    print(f"Details: {details}")
    response = input("Allow? (y/n): ").strip().lower()
    return response == "y"
