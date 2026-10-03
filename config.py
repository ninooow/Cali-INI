import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseModel):
    PROJECT_NAME: str = "CALI-INI Intelligent Manufacturing Backend"
    API_V1_PREFIX: str = "/api/v1"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        f"sqlite:///{BASE_DIR / 'calini.db'}"
    )
    WORKBOOK_PATH: str = os.getenv(
        "IM_WORKBOOK",
        str(BASE_DIR / "All_Case_Data.xlsx")
    )
    OUTPUT_DIR: str = os.getenv(
        "IM_OUTPUT_DIR",
        str(BASE_DIR / "dashboard_output_v10_10")
    )

settings = Settings()
