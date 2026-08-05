import speech_recognition as sr

def listen_for_command():
    recognizer = sr.Recognizer()
    # Fine-tuned parameters to make his hearing sharp and accurate
    recognizer.energy_threshold = 300 
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.8  # Wait slightly longer before assuming you're done speaking
    
    with sr.Microphone() as source:
        try:
            # Adjust quickly to background noise once per listening cycle
            recognizer.adjust_for_ambient_noise(source, duration=0.2)
            
            # Listen for up to 6 seconds timeout, 15 seconds phrase limit
            audio = recognizer.listen(source, timeout=6, phrase_time_limit=15)
            
            command = recognizer.recognize_google(audio).lower()
            return command
            
        except sr.WaitTimeoutError:
            return ""
        except sr.UnknownValueError:
            return ""
        except sr.RequestError:
            return ""