import os
import subprocess
import sys

def install_requirements():
    print("Installing required packages...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

def main():
    # Install requirements
    # install_requirements()
    
    # Run the scraper
    print("Starting manga scraper...")
    subprocess.check_call([sys.executable, "manga_scraper.py"])

if __name__ == "__main__":
    main()