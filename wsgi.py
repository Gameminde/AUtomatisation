from dashboard_app import create_app

app = create_app()

if __name__ == "__main__":
    import os
    port = int(os.getenv("DASHBOARD_PORT", 5000))
    app.run(host="0.0.0.0", port=port)
