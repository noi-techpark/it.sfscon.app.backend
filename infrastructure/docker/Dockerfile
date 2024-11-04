FROM python:3.12.7

ENV PYTHONUNBUFFERED 1

WORKDIR / 

COPY src .

RUN apt update

RUN apt install -y joe vim redis postgresql-client cron


RUN pip install --upgrade pip
RUN pip install wheel

COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY start.sh /start.sh
RUN chmod +x /start.sh

COPY ./src/scripts /scripts

CMD ["./start.sh"]
