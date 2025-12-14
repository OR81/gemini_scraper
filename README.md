# gemini_scraper
gemini scraper with python and selenium
### login:

curl --location 'http://127.0.0.1:8085/login_with_cookies' \
--header 'Content-Type: application/json' \
--data '{
    "version":"Fast",
    "cards":{
        "Create image":true,
        "Create video":false,
        "Write anything":false,
        "Help me learn":false,
        "Boost my day":false
    }

}'

### send prompt:
```
curl --location 'http://127.0.0.1:8085/send_prompt' \
--header 'Content-Type: application/json' \
--data '{  "prompt": "سلام یک  صفحه ی اچ تی ام ال ای راجع به آخرین خبر روز دنیا همراه با عکس و متن زیبا میخوام",
   "session_id": "46ad99e624674a71a4f391231e10d7c7" 
}'
```



### active driver's list:
```
curl --location 'http://127.0.0.1:5050/active_driver'
```

### logout
```
curl --location 'http://127.0.0.1:8085/close_driver' \
--header 'Content-Type: application/json' \
--data '{
    "session_id":"c0a9b4a81c044f91a4da35645779b983"
}'
```


