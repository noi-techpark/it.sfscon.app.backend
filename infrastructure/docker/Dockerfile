FROM python:3.11.5

ENV PYTHONUNBUFFERED 1

COPY src .

RUN apt update

RUN apt install -y joe vim redis postgresql-client


RUN pip install --upgrade pip
RUN pip install wheel

COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

