import requests 
import json
import time
import pika
#import build_new_activity_modified as buil_activity
from collections import defaultdict

current_time_ms = lambda: round(time.time() * 1000)


class WWSConnection:
  '''Creates a WWS connection via pika'''
  def __init__(self, server, port, vhost, username, password):
    print("Initialize WWS")
    self.credentials = pika.credentials.PlainCredentials(username, password)
    self.parameters  = pika.ConnectionParameters(server, port, vhost, self.credentials)
    self.connection  = pika.BlockingConnection(self.parameters)
    self.channel     = self.connection.channel()

  def send(self, message):
    print("Send: " + message.toJSON())
    self.channel.queue_declare(queue=message.get("to"))
    self.channel.basic_publish(exchange='ingress_exchange',    # ingress_exchange when sending, egress_exchange when receiving
                      routing_key=message.get("to"),
                      body=message.toJSON())

  def subscribe(self, what, callback):
    self.channel.queue_declare(queue=what)
    self.channel.queue_bind(what, exchange='egress_exchange', routing_key=what, arguments=None)
    self.channel.basic_consume(queue=what, on_message_callback=callback, auto_ack=True)
    self.channel.start_consuming()

  def close(self):
    print("Close WWS")
    self.connection.close()


class WWSMessage:
  '''Basic message blueprint structure for commands send to Eyebud'''
  def __init__(self, to):
    self.dict = {
      'time' : current_time_ms(),
      'v'    : "V2",
      'from' : "univhelsinki_cs_test",
      'to'   : to
    }

  def put(self, key, value):
    self.dict[key] = value

  def get(self, key):
    return self.dict[key]

  def toJSON(self):
    return json.dumps(self, default=lambda o: o.dict, sort_keys=True, indent=4)


class Eyebud():
  '''Defines Eyebud and relevant functions'''
  def __init__(self, id, wws):
    self.id  = id
    self.wws = wws

  def say(self, message):
    wwsmessage = WWSMessage(self.id + ".tts")
    wwsmessage.put("action", "say")
    wwsmessage.put("text", message)
    self.wws.send(wwsmessage)

  def prompt_voice(self):
    wwsmessage = WWSMessage(self.id + ".stt")
    wwsmessage.put("action", "start")
    wwsmessage.put("tone_responses", "on")
    wwsmessage.put("'tts_responses'", "'off'")
    self.wws.send(wwsmessage)

  def play_sound(self, sound):
    # sound = "Beep3.wav"
    wwsmessage = WWSMessage(self.id + ".audio.playback")
    wwsmessage.put("action", "start")
    wwsmessage.put("filename", sound)
    self.wws.send(wwsmessage)

  def subscribe(self, what, callback):
    self.wws.subscribe(self.id + '.' + what, callback)


def eyebud_speak(message):
    wws = WWSConnection(
        'wws.msv-project.com', 5672,
        '/test', 'flurdion', 'rfs745qr'
    )
    bud = Eyebud("BAN_V2", wws)

    bud.say(message)

    wws.close()

def writeToFile(filename, data):
    file = open(filename,"w")
    file.write(json.dumps(data).lower())
    file.close()

def main():
  while True:
    for i in range(10):
      url = 'https://reknowdesktopsurveillance.hiit.fi/speech.php'
      print('Analyzing image', i, 'from Eyebud')
      myobj = {'num': str(i)}
      x = requests.post(url, data = myobj)
      if x.text.strip()=="":
        img_url = "http://108.128.153.197:8181/photo/BAN_V2/"+str(i)
        headers = {'Content-Type': 'application/json'}
        payload = {
          "img_url":img_url,
          "engine":"vision"     
        }
        try:
          response = requests.post(
            'http://reknowdesktopsurveillance.hiit.fi:8888',
            headers=headers,
            data=json.dumps(payload)
            )
          translated = json.loads(response.text.strip()).get('Translation', "")
          texts = json.loads(response.text.strip()).get('Annotations', None)
          tags = json.loads(response.text.strip()).get('Tags', None)
          text = ''
          if 'description' in texts[0]:
            text = texts[0]['description']
          persons = defaultdict(int)
          others = defaultdict(int)
          if "entities" in tags:
            for entity in tags['entities']:
              if entity["type"] == "Person" :
                persons[entity["text"].replace(' ','_')] += 1
          if "keywords" in tags:
            for keyword in tags["keywords"]:
              others[keyword["text"].replace(' ','_')] += 1
          sorted_persons = sorted(persons, key=lambda k: len(k), reverse=True)
          sorted_others = sorted(others, key=lambda k: len(k), reverse=True)
          new_persons = []
          new_others = []
          for person in sorted_persons:
            if person.replace("_"," ") in text and len(person)>2:
              text = text.replace(person.replace("_"," "), person)
              for i in range(0, text.count(person)):
                new_persons.append(person)
                text = text.replace(person, "")
          for other in sorted_others:
            if other.replace("_"," ") in text and len(other)>2:
              text = text.replace(other.replace("_"," "), other)
              for i in range(0, text.count(other)):
                new_others.append(other)
                text = text.replace(other, "")
          if text.strip()!="" or len(new_persons)>0 or len(new_others)>0:
            filetowrite = str(time.time())+".txt"
            writeToFile('converted_withentities/'+filetowrite, text.lower().strip())
            writeToFile('persons/'+filetowrite, new_persons)
            writeToFile('keywords/'+filetowrite, new_others)
            print('Text detected')
            #buil_activity.main()
          else:
            print('Error! No text!', text.lower())
          #print(text.lower())
          #print(json.dumps(new_persons).lower())
          #print(json.dumps(new_others).lower())
        except Exception as e:
          print("HTML error of some kind", e)
        print('')
      else :
        eyebud_speak(x.text.strip())
        print(x.text.strip())
        new_persons = [x.text.strip().replace(' ', '_')]
        new_others = []
        if len(new_persons)>0:
          filetowrite = str(time.time())+".txt"
          writeToFile('converted_withentities/'+filetowrite, x.text.strip())
          writeToFile('persons/'+filetowrite, new_persons)
          writeToFile('keywords/'+filetowrite, new_others)
          #buil_activity.main()

if __name__ == '__main__':
    main()

  
