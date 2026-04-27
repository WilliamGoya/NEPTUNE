web: gunicorn 'app:create_app()' --bind 0.0.0.0:$PORT --workers 2 --timeout 60
worker: python fetcher.py
release: flask --app app db upgrade
