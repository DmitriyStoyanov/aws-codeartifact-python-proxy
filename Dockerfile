FROM python:3.7

WORKDIR /app
COPY requirements.txt /app
RUN pip3 install -r requirements.txt

COPY app.py /app

ENTRYPOINT ["python3"]
CMD ["app.py"]
EXPOSE 5000
