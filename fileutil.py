def savejson(dir,data):
  import json
  with open(dir, mode="wt", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
    return("Success")

def loadjson(dir):
  import json
  encoding = "utf-8"
  try:
    with open(dir, mode="rt", encoding="utf-8") as f:
     data = json.load(f)
    return(data)
  except:return("error")

def loadtxt(dir):

  with open(dir) as f:
      return(f.read())

def savetxt(dir,data):
  with open(dir, mode='w') as f:
      f.write(data)
      return("Success")
