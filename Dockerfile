FROM python

COPY . ./latte_bot

WORKDIR ./latte_bot

RUN pip install -r requirements.txt

CMD ["python", "./launcher.py"]