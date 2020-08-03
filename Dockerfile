FROM python:3
COPY . .

# We need wget to set up the PPA and unzip to install the Chromedriver
RUN apt-get install -y wget unzip

# Set up the Chrome PPA
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
RUN echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list

# Update the package list and install chrome
RUN apt-get update -y
RUN apt-get install -y google-chrome-stable

# Set up Chromedriver Environment variables
ENV CHROMEDRIVER_VERSION 2.19
ENV CHROMEDRIVER_DIR /usr/bin/

# Download and install Chromedriver
RUN wget -q --continue -P $CHROMEDRIVER_DIR "https://chromedriver.storage.googleapis.com/84.0.4147.30/chromedriver_linux64.zip"
RUN unzip $CHROMEDRIVER_DIR/chromedriver* -d $CHROMEDRIVER_DIR
RUN chmod a+x $CHROMEDRIVER_DIR/chromedriver

# Put Chromedriver into the PATH
#ENV PATH $CHROMEDRIVER_DIR:$PATH

RUN pip3 install pycountry pycountry_convert selenium requests jinja2 coloredlogs enlighten 
RUN python setup.py install
ENTRYPOINT ["instaloctrack"]
