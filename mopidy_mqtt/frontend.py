# future imports
from __future__ import absolute_import
from __future__ import unicode_literals

# stdlib imports
import logging
import time
import json

from mopidy import core

import paho.mqtt.client as mqtt

# third-party imports
import pykka

logger = logging.getLogger(__name__)

class MQTTFrontend(pykka.ThreadingActor, core.CoreListener):

    def __init__(self, config, core):
        logger.info("mopidy_mqtt initializing ... ")
        self.core = core
        self.mqttClient = mqtt.Client(client_id="mopidy-" + str(int(round(time.time() * 1000))), clean_session=True)
        self.mqttClient.on_message = self.mqtt_on_message
        self.mqttClient.on_connect = self.mqtt_on_connect     
        
        self.config = config['mqtthook']
        self.topic = self.config['topic']
        self.json_state = self.config['json_state']

        if self.config['username'] and self.config['password']:
            self.mqttClient.username_pw_set(self.config['username'], password=self.config['password'])

        host = self.config['mqtthost']
        port = self.config['mqttport']

        self.mqttClient.connect_async(host, port, 60)        
        
        self.mqttClient.loop_start()
        super(MQTTFrontend, self).__init__()
        self.MQTTHook = MQTTHook(self, core, config, self.mqttClient)
        
    def mqtt_on_connect(self, client, userdata, flags, rc):
        logger.info("Connected with result code %s" % rc)
        
        rc = self.mqttClient.subscribe(self.topic + "/play")
        if rc[0] != mqtt.MQTT_ERR_SUCCESS:            
            logger.warn("Error during subscribe: " + str(rc[0]))
        else:
            logger.info("Subscribed to " + self.topic + "/play")
#       self.mqttClient.subscribe(self.topic + "/control")
#        logger.info("sub:" + self.topic + "/control")
#        self.mqttClient.subscribe(self.topic + "/volume")
#       logger.info("sub:" + self.topic + "/volume")
#        self.mqttClient.subscribe(self.topic + "/add")
#        logger.info("sub:" + self.topic + "/add")
    		## Listen for request to refresh all data
        self.mqttClient.subscribe(self.topic + "/current_state")
        self.mqttClient.subscribe("hermes/intent/konjou:playAsong")
        logger.info("sub: hermes/intent/konjou:playAsong")
        self.mqttClient.subscribe("hermes/intent/konjou:playAnArtist")
        self.mqttClient.subscribe("hermes/intent/konjou:nextSong")
        self.mqttClient.subscribe("hermes/intent/previousSong")
        self.mqttClient.subscribe("hermes/intent/konjou:speakerInterrupt")
        self.mqttClient.subscribe("hermes/intent/konjou:resumeMusic")
        self.mqttClient.subscribe("hermes/intent/konjou:volumeDown")
        self.mqttClient.subscribe("hermes/intent/volumeUp")
		
    def mqtt_on_message(self, mqttc, obj, msg):
        logger.info("received a message on " + msg.topic+" with payload "+str(msg.payload))

        topCurrentState = self.topic + "/current_state"

        if msg.topic == "hermes/intent/konjou:speakerInterrupt":
            self.core.playback.pause()
        elif msg.topic == "hermes/intent/konjou:resumeMusic":
            self.core.playback.resume()
        elif msg.topic == "hermes/intent/konjou:nextSong":
            self.core.playback.next()
        elif msg.topic == "hermes/intent/previousSong":
            self.core.playback.previous()
        elif msg.topic == "hermes/intent/konjou:volumeDown":
            volume=10
            self.core.mixer.set_volume(volume)

        elif msg.topic == topCurrentState:
			      # Publish the current state
            self.send_state()
        elif msg.topic == "hermes/intent/konjou:playAsong":
			slots = self.parse_slots(msg)
			if 'artist' in slots:
				self.playSong(slots['song'],slots['artist'])
			else:
				self.playSong(slots['song'],"")
        elif msg.topic == "hermes/intent/konjou:playAnArtist":
			slots = self.parse_slots(msg)
			if 'artist' in slots:
				self.playArtist(slots['artist'])

    def send_state(self):
        current_track = self.core.playback.get_current_track().get()
        playback_state = self.core.playback.get_state().get()

        current_state = {
            "playback": playback_state,
            "timestamp": int(time.time())
        }
        if current_track:
          track_artist = list(current_track.artists)[0].name
          track_name = current_track.name
          track_uri = current_track.uri
          images = []
          imgUris = self.core.library.get_images([track_uri]).get()
          for k in imgUris:
            if len(imgUris[k]) > 0:
              images.append(imgUris[k][0].uri)
      
          image = None
          if len(images) > 0:
            image = images[0]

          current_state.update({
            "artist":track_artist,
            "name": track_name,
            "uri": track_uri,
            "image": image,
          })
          logger.info(current_state) 
        else:
          logger.info("Failed to get current track")
        self.MQTTHook.publish("/status",  current_state)

    def on_stop(self):
        logger.info("mopidy_mqtt shutting down ... ")
        self.mqttClient.disconnect()

    def playSong(self, songName, artistName):
		if artistName == "":
			result = self.core.library.search({'track_name':[songName]}).get()
		else:
			result = self.core.library.search({'track_name':[songName],'artist':[artistName]}).get()
		track = result[0].tracks   #get list of tracks from search results
		self.core.tracklist.clear().get()
		self.core.tracklist.add(None,0,track[0].uri,None).get()
		self.core.playback.play()

    def playArtist(self, artistname):
		result = self.core.library.search({'artist':[artistname]}).get()    #search for artist in all backends
		artist = result[0].tracks								#get list of tracks from artist search
		self.core.tracklist.clear().get()
		for track in artist:
			self.core.tracklist.add(None,0,track.uri,None).get()
			logger.info(track.name)
		self.core.tracklist.shuffle().get()
		self.core.playback.play()
		
    def playback_state_changed(self, old_state, new_state):
        self.send_state()
        #payload = new_state
        #if self.json_state:
        #    payload = {"old_state": old_state, "new_state": new_state}
        #self.MQTTHook.publish("/state", payload)
        #if (new_state == "stopped" and not self.json_state):
        #    self.MQTTHook.publish("/nowplaying", "stopped")
        

    def parse_slots(self, msg):
		data = json.loads(msg.payload)
		return dict((slot['slotName'], slot['value']['value']) for slot in data['slots'])   

class MQTTHook():
    def __init__(self, frontend, core, config, client):
        self.config = config['mqtthook']
        self.mqttclient = client

    def publish(self, topic, state):
        full_topic = self.config['topic'] + topic
        try:
            state = json.dumps(state)
            rc = self.mqttclient.publish(full_topic, state)
            if rc[0] == mqtt.MQTT_ERR_NO_CONN:            
                logger.warn("Error during publish: MQTT_ERR_NO_CONN")
            else:
                logger.info("Sent " + state + " to " + full_topic)
        except Exception as e:
            logger.error('Unable to send', exc_info=True) 
