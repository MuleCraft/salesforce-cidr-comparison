FROM ubuntu:22.04

RUN apt-get update && \
    apt-get install -y \
      curl python3 python3-pip unzip wget \
      openjdk-11-jdk maven

RUN curl -fsSL https://deb.nodesource.com/setup_16.x | bash - && \
    apt-get install -y nodejs

RUN npm install -g anypoint-cli

# Install Mule CE 4.4.0 (example version: adjust as needed)
RUN wget https://repository-master.mulesoft.org/nexus/content/repositories/releases/org/mule/distributions/mule-standalone/4.4.0/mule-standalone-4.4.0.tar.gz && \
    tar -xzf mule-standalone-4.4.0.tar.gz -C /opt && \
    ln -s /opt/mule-standalone-4.4.0 /opt/mule

ENV MULE_HOME=/opt/mule
ENV PATH="$PATH:/opt/mule/bin"

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

RUN pip3 install --no-cache-dir flask requests

COPY compare_cidr.py .

EXPOSE 8081

CMD ["python3", "compare_cidr.py"]
