# Nail Tinder

## Setup

The FastAPI environment is located in your home directory to avoid issues with the exfat filesystem:
- **Environment Path:** `/home/liza/.venvs/nail-tinder`

### To Activate the Environment
```bash
source /home/liza/.venvs/nail-tinder/bin/activate
```

### To Run the Server
1. **Move to the project directory:**
   ```bash
   cd /media/liza/B779-017B/nail-tinder
   ```
2. **Run with uvicorn:**
   ```bash
   uvicorn main:app --reload
   ```

**Alternatively**, run it directly with one command (if the port 8000 is free):
```bash
/home/liza/.venvs/nail-tinder/bin/python3 /media/liza/B779-017B/nail-tinder/main.py
```

## Troubleshooting
If you get an **"Address already in use"** error, run:
```bash
fuser -k 8000/tcp
```

## Dependencies
The project dependencies are also listed in `requirements.txt`.
