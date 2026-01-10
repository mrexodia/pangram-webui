import os

PANGRAM_API_KEY = os.getenv("PANGRAM_API_KEY")
if not PANGRAM_API_KEY:
    raise ValueError("PANGRAM_API_KEY is not set in environment variables.")

def main():
    print(f"Using PANGRAM_API_KEY: {PANGRAM_API_KEY}")


if __name__ == "__main__":
    main()
