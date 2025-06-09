import os
from dotenv import load_dotenv

load_dotenv()  # Load the .env file

print("GROK_API_KEY =", os.getenv("GROK_API_KEY"))

