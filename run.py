from pathlib import Path

from dotenv import load_dotenv

# gunicorn / python run.py 入口：在导入应用前先加载 .env
load_dotenv(Path(__file__).resolve().parent / ".env")
load_dotenv()

from app import create_app

app = create_app()

if __name__ == "__main__":
    # 仅本机可访问；局域网调试可改为 0.0.0.0
    app.run(host="127.0.0.1", port=5000, debug=True)
