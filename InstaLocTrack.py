from selenium import webdriver
import time
import re
import json
import requests
import sys
import asyncio 
from concurrent.futures import ThreadPoolExecutor

if len(sys.argv) < 2:
  print("Usage: python3 instaloctrack.py <username>")
  exit()

username = sys.argv[1] #Instagram account to investigate
browser = webdriver.Chrome('/usr/bin/chromedriver')
browser.get('https://www.instagram.com/'+username+'/?hl=fr')

number_publications = browser.find_element_by_xpath("/html/body").text.strip().split("\n")[3].split(" ")[0] 

def scrolls(publications): # scrolls required to snag all the data accordingly to the number of posts
    return (int(publications))//11
    #return 1 #for testing purpose

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

def parse_location_timestamp(content):
    location = []
    try:
        address = re.search(r'\\/explore\\/locations\\/[0-9]+\\/([^/]+)\\/', content).group(1).replace("-", " ")
    except:
        address= "Error"
    
    try:
        city = re.search('"addressLocality":"([^"]+)"', content)[0].split(":")[1].split(",")[0].replace("\"", "")
    except:
        city = "Error"
    
    try:
        countrycode = re.search('Country","name":"([^"]+)"', content)[0].split(":")[1].replace("\"", "")
    except:
        countrycode = "Error"
    
    location.extend([address, city, countrycode])

    if location != ["Error", "Error", "Error"]:
        tmp_timestamp = re.search('"uploadDate":"([^"]+)"', content)[0].split('T')[0]
        return [location,re.sub('[^0-9\-]', '', tmp_timestamp)]
    else:
        return None

def fetch_locations_and_timestamps(links):
  sys.stdout.write("\033[K")
  max_wrk = 50
  print("Fetching Locations and Timestamps on each picture ... " + str(len(links)) + " links processed asynchronously by a pool of " + str(max_wrk) , end="\r")
  executor = ThreadPoolExecutor(max_workers=max_wrk) # didnt find any information about Instagram / Facebook Usage Policy ... people on stackoverflow say there's no limit if you're not using any API so ... ¯\_(ツ)_/¯
  loop = asyncio.get_event_loop()

  async def make_requests():
    futures = [loop.run_in_executor(executor, requests.get, 'https://www.instagram.com/p/' + url) for url in links]
    await asyncio.wait(futures)
    return futures

  links_locations_timestamps = []
  futures = loop.run_until_complete(make_requests())
  number_locs = len(futures)
  count = 0

  for i in range(0, number_locs):
    content = futures[i].result().text
    location_timestamp = parse_location_timestamp(content)
    if location_timestamp != None:
      count += 1
      links_locations_timestamps.append(['https://www.instagram.com/p/'+links[i], location_timestamp[0], location_timestamp[1]])
      
    print("Parsing location data ... " + str(i) + "/" + str(number_locs) + " links processed... " + " Found location data on " + str(count) + " links" , end="\r")
  return links_locations_timestamps

def geocode(location):
    query = "https://nominatim.openstreetmap.org/search?"
    # if location[0] != "Error":
    #     query += "street=" + location[0] + "&"
    if location[1] != "Error":
        query += "city=" + location[1] + "&"
    if location[2] != "Error":
        query += "countrycode=" + location[2] + "&"
    print(query + "format=json&limit=1")
    return requests.get(query + "&format=json&limit=1").json()[0]

def geocode_all(links_locations_and_timestamps):
  sys.stdout.write("\033[K")
  errors = 0
  count = 1
  gps_coordinates = []

  for location in links_locations_and_timestamps:
      print("Fetching GPS Coordinates ... : Processing location number " + str(count) + " out of " + str(len(links_locations_and_timestamps)) + " - Number of errors:" + str(errors), end="\r")
      try:
          tmp_geoloc = geocode(location[1])
          gps_coordinates.append([tmp_geoloc['lat'], tmp_geoloc['lon']])
      except:
          print("An exception occurred for: " + str(location[1]))
          errors+=1
          gps_coordinates.append("Error")
      time.sleep(1) # Respect Normatim's Usage Policy! (1 request per sec max) https://operations.osmfoundation.org/policies/nominatim/
      count+=1
      
  sys.stdout.write("\033[K")

  return gps_coordinates

def export_data(links_locations_and_timestamps, gps_coordinates):

  json_dump = []
  errors = []

  for i in range(0, len(links_locations_and_timestamps)):
    links_locations_and_timestamps[i].append(gps_coordinates[i])
    if gps_coordinates[i] != "Error":
      json_dump.append({"link" : links_locations_and_timestamps[i][0],"place" : links_locations_and_timestamps[i][1], "timestamp" : links_locations_and_timestamps[i][2], "gps" : {"lat" : links_locations_and_timestamps[i][3][0] ,  "lon" : links_locations_and_timestamps[i][3][1]}})
    else:
      errors.append(({"link" : links_locations_and_timestamps[i][0],"place" : links_locations_and_timestamps[i][1], "timestamp" : links_locations_and_timestamps[i][2], "gps" : "Error"}))
  with open(username + '_instaloctrack_data.json', 'w') as filehandle:
    json.dump(json_dump, filehandle)

  with open(username + '_instaloctrack_errors.json', 'w') as filehandle:
    json.dump(errors, filehandle)
  print("Location names, timestamps, and GPS Coordinates were writtent to : " + username + '_instaloctrack_data.json')

def draw_map(gps_coordinates):

  map = """
  <html>
  <head>
    
    <title>Google Maps Multiple Markers</title>
    <script src="http://maps.google.com/maps/api/js?sensor=false" type="text/javascript"></script>
  </head>
  <body>
    <ul style="list-style-type:square;">
      <li>Instagram profile: """ +   """ <a href= """ + "https://www.instagram.com/" + username + """>""" + "@"+ username  +"""</a></li>
      <li>Number of locations mapped: """ + str(len(links_locations_and_timestamps)) + """</li>
    </ul>
    <div id="infos"> </div>
    <div id="map" style="height: 400px; width: 500px;">
  </div>
  <script type="text/javascript">
      var links = """ + str([x[0] for x in links_locations_and_timestamps]) + """;
      var places = """ + str([x[1] for x in links_locations_and_timestamps]) + """;
      var timestamps = """ + str([x[2] for x in links_locations_and_timestamps]) + """;
      var locations = """ + str(gps_coordinates) + """;

      var map = new google.maps.Map(document.getElementById('map'), {
        zoom: 1,
        center: new google.maps.LatLng(48.866667, 2.333333),
        mapTypeId: google.maps.MapTypeId.ROADMAP
      });

      var infowindow = new google.maps.InfoWindow();

      var marker, i;

      for (i = 0; i < locations.length; i++) { 
        marker = new google.maps.Marker({
          position: new google.maps.LatLng(locations[i][0], locations[i][1]),
          map: map,
        });

        google.maps.event.addListener(marker, 'click', (function(marker, i) {
          return function() {

             html =  '<ul style="list-style-type:square;">'
             html += '<li>Picture link: <a href=' + links[i] + '>Link</a></li>'
             html += '<li>Place name: ' + places[i] + '</li>'
             html += '<li>Timestamp: ' + timestamps[i] + '</li>'
             html += '<li>Lattitude: ' + locations[i][0] + '</li>'
             html += '<li>Longitude: ' + locations[i][1] + '</li>'
             html += '</ul>'
             infowindow.setContent(html);
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
  print("Map with all the markers was written to: " + username + '_instaloctrack_map.html')

links = fetch_urls(number_publications)
browser.quit()
links_locations_and_timestamps = fetch_locations_and_timestamps(links)
gps_coordinates = geocode_all(links_locations_and_timestamps)
export_data(links_locations_and_timestamps, gps_coordinates)
draw_map(gps_coordinates)