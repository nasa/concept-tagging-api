FROM python:3.7

# Install dependencies
USER root
COPY requirements.txt /home/requirements.txt
RUN pip install -r /home/requirements.txt
ARG cachebust=2
RUN pip install git+https://github.com/nasa/concept-tagging-training.git@v1.0.3-open_source_release
RUN python -m spacy download en_core_web_sm

# Include src and set permissions
RUN mkdir /home/service
COPY service home/service
WORKDIR home/

# Label image with git commit url
ARG GIT_URL=unspecified
ARG VERSION=unspecified
LABEL org.label-schema.schema-version=1.0
LABEL org.label-schema.url=$GIT_URL
LABEL org.label-schema.version=$VERSION
ENV VERSION=$VERSION
ENV MODELS_DIR=models/experiment

# Set service to a user
RUN groupadd -g 999 appuser && \
    useradd -r -u 999 -g appuser appuser
RUN chown -R 999:999 /home/service
USER appuser
WORKDIR /home/service

ENV PRELOAD=True 
# Change PRELOAD to False to load models for each request.
# Saves RAM with little effect on bulk requests
# but a large effect on small requests.
EXPOSE 5000
ENTRYPOINT ["gunicorn", "app:app", "-b", " 0.0.0.0:5000"]
CMD ["--timeout", "1200"]
