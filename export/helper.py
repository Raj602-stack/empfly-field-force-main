def check_key_exist(keys:list, hashmap):
    if not hashmap:
        return "NA"

    for i in keys:
        hashmap = hashmap.get(i, None)
        if hashmap == None:
            return "NA"
    
    return hashmap

get_or_return_NA = lambda value: "" if value == None  else value