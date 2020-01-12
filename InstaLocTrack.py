from selenium import webdriver
import time
import re
import json
import requests
import sys

if len(sys.argv) < 2:
  print("Usage: python3 instaloctrack.py <username>")
  exit()

username = sys.argv[1] #Instagram account to investigate
browser = webdriver.Chrome('/usr/bin/chromedriver')
browser.get('https://www.instagram.com/'+username+'/?hl=fr')

number_publications = browser.find_element_by_xpath("/html/body").text.strip().split("\n")[3].split(" ")[0] 

def scrolls(publications): # scrolls required to snag all the data accordingly to the number of posts
    return (int(publications))//11
    #return 1

def fetch_urls(number_publications):
  links = []
  links.extend(re.findall('/p/([^/]+)/', browser.page_source)) 
  n_scrolls = scrolls(number_publications)

  for i in range(n_scrolls): # collecting all the pictures links in order to see which ones contains location data
    print("Scrolling the Instagram profile, fetching pictures URLs ..." + str(100*i//n_scrolls) + "% of the profile scrolled ", end="\r")
    browser.execute_script("window.scrollTo(0, document.body.scrollHeight)")
    links.extend(re.findall('/p/([^/]+)/', browser.page_source)) 
    time.sleep(1) # dont change this, otherwise some scrolls won't be effective and all the data won't be scrapped

  return list(dict.fromkeys(links)) # remove duplicates

def fetch_locations_and_timestamps(links):
  sys.stdout.write("\033[K")
  locations_and_timestamps = []
  counter = 1
  for link in links: # iterate over the links, collect location and timestamps if a location is available on the Instagram post
      print("Checking Locations on each picture : Picture " + str(counter) + " out of " + str(len(links)) + " - " + str(len(locations_and_timestamps)) + " Locations collected", end="\r")
      browser.get('https://www.instagram.com/p/'+link)
      tmp_loc = re.search('/explore/locations/[0-9]+/([^/]+)/', browser.page_source)
      if tmp_loc != None:
        tmp_timestamp = re.search('datetime="([^"]+)"', browser.page_source)[0].split('T')[0]
        locations_and_timestamps.append([tmp_loc.group(1).replace('-', ' '), re.sub('[^0-9\-]', '', tmp_timestamp)])
      counter+=1
  return locations_and_timestamps

def geocode(location):
    return requests.get("https://nominatim.openstreetmap.org/search?q=" + location[0] + "&format=json&limit=1").json()[0]

def geocode_all(locations_and_timestamps):
  sys.stdout.write("\033[K")
  errors = 0
  count = 1
  gps_coordinates = []

  for location in locations_and_timestamps:
      print("Fetching GPS Coordinates ... : Processing location number " + str(count) + " out of " + str(len(locations_and_timestamps)) + " - Number of errors:" + str(errors), end="\r")
      try:
          tmp_geoloc = geocode(location)
          gps_coordinates.append([tmp_geoloc['lat'], tmp_geoloc['lon']])
      except:
          print("An exception occurred for: " + location[0])
          errors+=1
          gps_coordinates.append("Error")
      time.sleep(1) # Respect Normatim's Usage Policy! (1 request per sec max) https://operations.osmfoundation.org/policies/nominatim/
      count+=1
      
  sys.stdout.write("\033[K")

  return gps_coordinates

def export_data(locations_and_timestamps, gps_coordinates):

  json_dump = []

  for i in range(0, len(locations_and_timestamps)):
    locations_and_timestamps[i].append(gps_coordinates[i])
    if gps_coordinates[i] != "Error":
      json_dump.append({"place" : locations_and_timestamps[i][0], "timestamp" : locations_and_timestamps[i][1], "gps" : {"lat" : locations_and_timestamps[i][2][0] ,  "lon" : locations_and_timestamps[i][2][1]}})
    
  with open(username + '_instaloctrack_data.json', 'w') as filehandle:
    json.dump(json_dump, filehandle)
  print("Location names, timestamps, and GPS Coordinates were writtent to :" + username + '_instaloctrack_data.json')
  

# gerer le cas d'erreur "Error dans les GPS pour eviter l'overflow de list, et gerer le print "

def draw_map(gps_coordinates):

  map = """
  <html>
  <head>
    
    <title>Google Maps Multiple Markers</title>
    <script src="http://maps.google.com/maps/api/js?sensor=false" type="text/javascript"></script>
  </head>
  <body>
    <div id="map" style="height: 400px; width: 500px;">
  </div>
  <script type="text/javascript">
      var locations = """ + str(gps_coordinates) + """;
      var timestamps = """ + str([x[1] for x in locations_and_timestamps]) + """;

      var map = new google.maps.Map(document.getElementById('map'), {
        zoom: 10,
        center: new google.maps.LatLng(48.866667, 2.333333),
        mapTypeId: google.maps.MapTypeId.ROADMAP
      });

      var infowindow = new google.maps.InfoWindow();

      var marker, i;

      for (i = 0; i < locations.length; i++) { 
        marker = new google.maps.Marker({
          position: new google.maps.LatLng(locations[i][0], locations[i][1]),
          timestamp: timestamps[i],
          map: map,
        });

        google.maps.event.addListener(marker, 'click', (function(marker, i) {
          return function() {
            infowindow.setContent(locations[i][0]);
            infowindow.open(map, marker);
          }
        })(marker, i));
      }
    </script>
  </body>
  </html>
  """

  mapfile = open(username + "_instaloctrack_map.html", "w")
  mapfile.write(map)
  mapfile.close()
  print("Map with all the markers was written to:" + username + '_instaloctrack_map.html')

links = fetch_urls(number_publications)
locations_and_timestamps = fetch_locations_and_timestamps(links)
gps_coordinates = geocode_all(locations_and_timestamps)
export_data(locations_and_timestamps, gps_coordinates)
draw_map(gps_coordinates)