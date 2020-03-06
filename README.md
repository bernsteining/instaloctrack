
# Insta LocTrack

## Goal of the project
The goal of this project is to collect all the locations linked to the photos of an Instagram profile in order to place them on a map.

I doesn't use Instagram's API since Instagram deprecated its location functionality in 2018, and also because I wanted to play with Selenium and Chromedriver to make my own scraper.

## requirements

sudo apt install chromium-chromedriver &&
sudo pip install -r requirements

## installation

```
git clone https://github.com/bernsteining/InstaLocTrack
cd InstaLocTrack
pip3 install .
```

## Usage

    python3 InstaLocTrack.py -h
    usage: InstaLocTrack [-h] [-t TARGET_ACCOUNT] [-l LOGIN] [-p PASSWORD] [-v]
    
    Instagram location data gathering tool. Usage: python3 InstaLocTrack.py -t <target_account>
    
    optional arguments:
      -h, --help            show this help message and exit
      -t TARGET_ACCOUNT, --target TARGET_ACCOUNT
                            Instagram profile to investigate
      -l LOGIN, --login LOGIN
                            Instagram profile to connect to, in order to access
                            the instagram posts of the target account
      -p PASSWORD, --password PASSWORD
                            Password of the Instagram profile to connect to
      -v, --visual          Spawns Chromium GUI, otherwise Chromium is headless


## How it works

First, we retrieve all the pictures links of the account by scrolling the whole Instagram profile, thanks to selenium's webdriver.

Then, we retrieve asynchronously (asyncio) each picture link, we check if it contains a location in the picture description, and retrieve the location's data if there's one, and the timestamp.

* **NB:** Since 2018 Instagram deprecated its location API and it's not possible anymore to get the GPS coordinates of a picture, all we can retrieve is the name of the location. (If you can prove me that I'm wrong about this, please tell me!)

Because Instagram doesn't provide GPS coordinates, and we're only given names of places, we have to geocode these (.ie. get the GPS coords from the name's place).

For this, I used Nominatim's awesome API, which uses OpenStreetMap. For our usage, no API key is required, and we respect [Nominatim's usage Policy](https://operations.osmfoundation.org/policies/nominatim/) by requesting GPS coordinatess once every second.

Eventually, once we have all the GPS coordinatess, we generate a HTML (thanks to jinja2 templating) with Javascript embedded that plots an Open Street Map (thanks to [Leaflet](https://github.com/Leaflet/Leaflet) library) with all our locations pinned. Once again, no API key is required for this step.

Also, the data collected by the script (location names, timestamps, GPS coordinates, errors) are dumped to a JSON file in order to be re-used.

## Example

As an example, here's the output on the former French President's Instagram profile, [@fhollande](https://www.instagram.com/fhollande/?hl=fr) :

![Map of @fhollande's locations on Instagram](https://i.imgur.com/5CwGElj.png
)

![Heatmap of @fhollande's locations on Instagram](https://i.imgur.com/vS4tZa1.png)

Information available when clicking on a marker:

![available data when clicking on a marker](https://imgur.com/QBIofFs.png)

The JSON data dump (just a part of it to show the format for a given location):

    {
        "link": "https://www.instagram.com/p/-Q_9EvR9eu",
        "place": {
          "id": "290297",
          "name": "Musée du quai Branly - Jacques Chirac",
          "slug": "musee-du-quai-branly-jacques-chirac",
          "street_address": " 37 quai Branly",
          " zip_code": " 75007",
          " city_name": " Paris",
          " region_name": " ",
          " country_code": " FR"
        },
        "timestamp": "2015-11-19",
        "gps": {
          "lat": "48.8566969",
          "lon": "2.3514616"
        }
      }




## Possible Improvements

* Cleaner code :D
* Use a logger instead of printing 
* Use requests asynchronously even in the logged on use case
* Check password correctness with -p flag
* Correct ISO Code for some countries: Nominatim doesn't considers French Polynesia's ISO  (or DOM TOM) code as valid for some reason ¯\\_(ツ)_/¯
* Provide statistics about the location data (most visited place, diagrams ...)
* Interactive dashboard instead of static html/JS output
* Better Geocoding :
	* Get GPS coords from Instagram's location ID ... doesn't work asynchronously at the moment, gotta check for the timeout settings, maybe use this just to correct the errors
	* Retry Geocoding when it fails because of the first field: happens when it's too precise, then the location of the city rather than the exact place would be better than just an error imo.
	* Use other geocoding tools (e.g. https://geo.api.gouv.fr/adresse) than Nominatim when it fails? (specify arg?)
	* Use [geopy](https://pypi.org/project/geopy/)
* Add an argument to select only a set of pictures (selected by date, or rank)
* Use GeoJSON WGS-84 (EPSG 4326) format
* Time information about the duration of the script
* The whole Instagram profile isn't scrolled if your connection is slow ... maybe gonna add a parameter to correct this
