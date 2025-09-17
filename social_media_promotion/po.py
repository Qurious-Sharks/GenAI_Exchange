from google.cloud import speech
from dotenv import load_dotenv
load_dotenv()
client = speech.SpeechClient()
print("Service account authenticated:", client)
