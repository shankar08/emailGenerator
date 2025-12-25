import sys
import os

# Add src/ folder to path for imports to work
ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.path.join(ROOT, "src")
if SRC_PATH not in sys.path:
    sys.path.append(SRC_PATH)

# Import the real Streamlit app
from ui.streamlit_app import main

if __name__ == "__main__":
    main()
