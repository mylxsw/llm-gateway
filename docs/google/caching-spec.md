Context caching allows you to save and reuse precomputed input tokens that you wish to use repeatedly, for example when asking different questions about the same media file. This can lead to cost and speed savings, depending on the usage. For a detailed introduction, see the[Context caching](https://ai.google.dev/gemini-api/docs/caching)guide.  

## Method: cachedContents.create

- [Endpoint](https://ai.google.dev/api/caching#body.HTTP_TEMPLATE)
- [Request body](https://ai.google.dev/api/caching#body.request_body)
- [Response body](https://ai.google.dev/api/caching#body.response_body)
- [Example request](https://ai.google.dev/api/caching#body.codeSnippets)
  - [Basic](https://ai.google.dev/api/caching#body.codeSnippets.group)
  - [From name](https://ai.google.dev/api/caching#body.codeSnippets.group_1)
  - [From chat](https://ai.google.dev/api/caching#body.codeSnippets.group_2)

Creates CachedContent resource.  

### Endpoint

post`https:``/``/generativelanguage.googleapis.com``/v1beta``/cachedContents`  

### Request body

The request body contains an instance of[CachedContent](https://ai.google.dev/api/caching#CachedContent).
Fields`contents[]``object (`[Content](https://ai.google.dev/api/caching#Content)`)`  
Optional. Input only. Immutable. The content to cache.
`tools[]``object (`[Tool](https://ai.google.dev/api/caching#Tool)`)`  
Optional. Input only. Immutable. A list of`Tools`the model may use to generate the next response  
`expiration``Union type`  
Specifies when this resource will expire.`expiration`can be only one of the following:
`expireTime``string (`[Timestamp](https://protobuf.dev/reference/protobuf/google.protobuf/#timestamp)` format)`  
Timestamp in UTC of when this resource is considered expired. This is*always*provided on output, regardless of what was sent on input.

Uses RFC 3339, where generated output will always be Z-normalized and use 0, 3, 6 or 9 fractional digits. Offsets other than "Z" are also accepted. Examples:`"2014-10-02T15:01:23Z"`,`"2014-10-02T15:01:23.045123456Z"`or`"2014-10-02T15:01:23+05:30"`.
`ttl``string (`[Duration](https://protobuf.dev/reference/protobuf/google.protobuf/#duration)` format)`  
Input only. New TTL for this resource, input only.

A duration in seconds with up to nine fractional digits, ending with '`s`'. Example:`"3.5s"`.
`displayName``string`  
Optional. Immutable. The user-generated meaningful display name of the cached content. Maximum 128 Unicode characters.
`model``string`  
Required. Immutable. The name of the`Model`to use for cached content Format:`models/{model}`
`systemInstruction``object (`[Content](https://ai.google.dev/api/caching#Content)`)`  
Optional. Input only. Immutable. Developer set system instruction. Currently text only.
`toolConfig``object (`[ToolConfig](https://ai.google.dev/api/caching#ToolConfig)`)`  
Optional. Input only. Immutable. Tool config. This config is shared for all tools.  

### Example request

### Basic

### Python

    from google import genai
    from google.genai import types

    client = genai.Client()
    document = client.files.upload(file=media / "a11.txt")
    model_name = "gemini-1.5-flash-001"

    cache = client.caches.create(
        model=model_name,
        config=types.CreateCachedContentConfig(
            contents=[document],
            system_instruction="You are an expert analyzing transcripts.",
        ),
    )
    print(cache)

    response = client.models.generate_content(
        model=model_name,
        contents="Please summarize this transcript",
        config=types.GenerateContentConfig(cached_content=cache.name),
    )
    print(response.text)  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/python/cache.py#L25-L46

### Node.js

    // Make sure to include the following import:
    // import {GoogleGenAI} from '@google/genai';
    const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
    const filePath = path.join(media, "a11.txt");
    const document = await ai.files.upload({
      file: filePath,
      config: { mimeType: "text/plain" },
    });
    console.log("Uploaded file name:", document.name);
    const modelName = "gemini-1.5-flash-001";

    const contents = [
      createUserContent(createPartFromUri(document.uri, document.mimeType)),
    ];

    const cache = await ai.caches.create({
      model: modelName,
      config: {
        contents: contents,
        systemInstruction: "You are an expert analyzing transcripts.",
      },
    });
    console.log("Cache created:", cache);

    const response = await ai.models.generateContent({
      model: modelName,
      contents: "Please summarize this transcript",
      config: { cachedContent: cache.name },
    });
    console.log("Response text:", response.text);  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/javascript/cache.js#L33-L62

### Go

    ctx := context.Background()
    client, err := genai.NewClient(ctx, &genai.ClientConfig{
    	APIKey:  os.Getenv("GEMINI_API_KEY"), 
    	Backend: genai.BackendGeminiAPI,
    })
    if err != nil {
    	log.Fatal(err)
    }

    modelName := "gemini-1.5-flash-001"
    document, err := client.Files.UploadFromPath(
    	ctx, 
    	filepath.Join(getMedia(), "a11.txt"), 
    	&genai.UploadFileConfig{
    		MIMEType : "text/plain",
    	},
    )
    if err != nil {
    	log.Fatal(err)
    }
    parts := []*genai.Part{
    	genai.NewPartFromURI(document.URI, document.MIMEType),
    }
    contents := []*genai.Content{
    	genai.NewContentFromParts(parts, genai.RoleUser),
    }
    cache, err := client.Caches.Create(ctx, modelName, &genai.CreateCachedContentConfig{
    	Contents: contents,
    	SystemInstruction: genai.NewContentFromText(
    		"You are an expert analyzing transcripts.", genai.RoleUser,
    	),
    })
    if err != nil {
    	log.Fatal(err)
    }
    fmt.Println("Cache created:")
    fmt.Println(cache)

    // Use the cache for generating content.
    response, err := client.Models.GenerateContent(
    	ctx,
    	modelName,
    	genai.Text("Please summarize this transcript"),
    	&genai.GenerateContentConfig{
    		CachedContent: cache.Name,
    	},
    )
    if err != nil {
    	log.Fatal(err)
    }
    printResponse(response)  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/go/cache.go#L16-L66

### Shell

    wget https://storage.googleapis.com/generativeai-downloads/data/a11.txt
    echo '{
      "model": "models/gemini-1.5-flash-001",
      "contents":[
        {
          "parts":[
            {
              "inline_data": {
                "mime_type":"text/plain",
                "data": "'$(base64 $B64FLAGS a11.txt)'"
              }
            }
          ],
        "role": "user"
        }
      ],
      "systemInstruction": {
        "parts": [
          {
            "text": "You are an expert at analyzing transcripts."
          }
        ]
      },
      "ttl": "300s"
    }' > request.json

    curl -X POST "https://generativelanguage.googleapis.com/v1beta/cachedContents?key=$GEMINI_API_KEY" \
     -H 'Content-Type: application/json' \
     -d @request.json \
     > cache.json

    CACHE_NAME=$(cat cache.json | grep '"name":' | cut -d '"' -f 4 | head -n 1)

    curl -X POST "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-001:generateContent?key=$GEMINI_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{
          "contents": [
            {
              "parts":[{
                "text": "Please summarize this transcript"
              }],
              "role": "user"
            },
          ],
          "cachedContent": "'$CACHE_NAME'"
        }'  
    https://github.com/google-gemini/deprecated-generative-ai-python/blob/7a7cc5474ddaa0255a4410e05361028a24400abd/samples/rest/cache.sh#L10-L59

### From name

### Python

    from google import genai
    from google.genai import types

    client = genai.Client()
    document = client.files.upload(file=media / "a11.txt")
    model_name = "gemini-1.5-flash-001"

    cache = client.caches.create(
        model=model_name,
        config=types.CreateCachedContentConfig(
            contents=[document],
            system_instruction="You are an expert analyzing transcripts.",
        ),
    )
    cache_name = cache.name  # Save the name for later

    # Later retrieve the cache
    cache = client.caches.get(name=cache_name)
    response = client.models.generate_content(
        model=model_name,
        contents="Find a lighthearted moment from this transcript",
        config=types.GenerateContentConfig(cached_content=cache.name),
    )
    print(response.text)  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/python/cache.py#L52-L75

### Node.js

    // Make sure to include the following import:
    // import {GoogleGenAI} from '@google/genai';
    const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
    const filePath = path.join(media, "a11.txt");
    const document = await ai.files.upload({
      file: filePath,
      config: { mimeType: "text/plain" },
    });
    console.log("Uploaded file name:", document.name);
    const modelName = "gemini-1.5-flash-001";

    const contents = [
      createUserContent(createPartFromUri(document.uri, document.mimeType)),
    ];

    const cache = await ai.caches.create({
      model: modelName,
      config: {
        contents: contents,
        systemInstruction: "You are an expert analyzing transcripts.",
      },
    });
    const cacheName = cache.name; // Save the name for later

    // Later retrieve the cache
    const retrievedCache = await ai.caches.get({ name: cacheName });
    const response = await ai.models.generateContent({
      model: modelName,
      contents: "Find a lighthearted moment from this transcript",
      config: { cachedContent: retrievedCache.name },
    });
    console.log("Response text:", response.text);  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/javascript/cache.js#L71-L102

### Go

    ctx := context.Background()
    client, err := genai.NewClient(ctx, &genai.ClientConfig{
    	APIKey:  os.Getenv("GEMINI_API_KEY"),
    	Backend: genai.BackendGeminiAPI,
    })
    if err != nil {
    	log.Fatal(err)
    }

    modelName := "gemini-1.5-flash-001"
    document, err := client.Files.UploadFromPath(
    	ctx, 
    	filepath.Join(getMedia(), "a11.txt"), 
    	&genai.UploadFileConfig{
    		MIMEType : "text/plain",
    	},
    )
    if err != nil {
    	log.Fatal(err)
    }
    parts := []*genai.Part{
    	genai.NewPartFromURI(document.URI, document.MIMEType),
    }
    contents := []*genai.Content{
    	genai.NewContentFromParts(parts, genai.RoleUser),
    }
    cache, err := client.Caches.Create(ctx, modelName, &genai.CreateCachedContentConfig{
    	Contents:          contents,
    	SystemInstruction: genai.NewContentFromText(
    		"You are an expert analyzing transcripts.", genai.RoleUser,
    	),
    })
    if err != nil {
    	log.Fatal(err)
    }
    cacheName := cache.Name

    // Later retrieve the cache.
    cache, err = client.Caches.Get(ctx, cacheName, &genai.GetCachedContentConfig{})
    if err != nil {
    	log.Fatal(err)
    }

    response, err := client.Models.GenerateContent(
    	ctx,
    	modelName,
    	genai.Text("Find a lighthearted moment from this transcript"),
    	&genai.GenerateContentConfig{
    		CachedContent: cache.Name,
    	},
    )
    if err != nil {
    	log.Fatal(err)
    }
    fmt.Println("Response from cache (create from name):")
    printResponse(response)  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/go/cache.go#L76-L131

### From chat

### Python

    from google import genai
    from google.genai import types

    client = genai.Client()
    model_name = "gemini-1.5-flash-001"
    system_instruction = "You are an expert analyzing transcripts."

    # Create a chat session with the given system instruction.
    chat = client.chats.create(
        model=model_name,
        config=types.GenerateContentConfig(system_instruction=system_instruction),
    )
    document = client.files.upload(file=media / "a11.txt")

    response = chat.send_message(
        message=["Hi, could you summarize this transcript?", document]
    )
    print("\n\nmodel:  ", response.text)
    response = chat.send_message(
        message=["Okay, could you tell me more about the trans-lunar injection"]
    )
    print("\n\nmodel:  ", response.text)

    # To cache the conversation so far, pass the chat history as the list of contents.
    cache = client.caches.create(
        model=model_name,
        config={
            "contents": chat.get_history(),
            "system_instruction": system_instruction,
        },
    )
    # Continue the conversation using the cached content.
    chat = client.chats.create(
        model=model_name,
        config=types.GenerateContentConfig(cached_content=cache.name),
    )
    response = chat.send_message(
        message="I didn't understand that last part, could you explain it in simpler language?"
    )
    print("\n\nmodel:  ", response.text)  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/python/cache.py#L81-L120

### Node.js

    // Make sure to include the following import:
    // import {GoogleGenAI} from '@google/genai';
    const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
    const modelName = "gemini-1.5-flash-001";
    const systemInstruction = "You are an expert analyzing transcripts.";

    // Create a chat session with the system instruction.
    const chat = ai.chats.create({
      model: modelName,
      config: { systemInstruction: systemInstruction },
    });
    const filePath = path.join(media, "a11.txt");
    const document = await ai.files.upload({
      file: filePath,
      config: { mimeType: "text/plain" },
    });
    console.log("Uploaded file name:", document.name);

    let response = await chat.sendMessage({
      message: createUserContent([
        "Hi, could you summarize this transcript?",
        createPartFromUri(document.uri, document.mimeType),
      ]),
    });
    console.log("\n\nmodel:", response.text);

    response = await chat.sendMessage({
      message: "Okay, could you tell me more about the trans-lunar injection",
    });
    console.log("\n\nmodel:", response.text);

    // To cache the conversation so far, pass the chat history as the list of contents.
    const chatHistory = chat.getHistory();
    const cache = await ai.caches.create({
      model: modelName,
      config: {
        contents: chatHistory,
        systemInstruction: systemInstruction,
      },
    });

    // Continue the conversation using the cached content.
    const chatWithCache = ai.chats.create({
      model: modelName,
      config: { cachedContent: cache.name },
    });
    response = await chatWithCache.sendMessage({
      message:
        "I didn't understand that last part, could you explain it in simpler language?",
    });
    console.log("\n\nmodel:", response.text);  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/javascript/cache.js#L111-L161

### Go

    ctx := context.Background()
    client, err := genai.NewClient(ctx, &genai.ClientConfig{
    	APIKey:  os.Getenv("GEMINI_API_KEY"),
    	Backend: genai.BackendGeminiAPI,
    })
    if err != nil {
    	log.Fatal(err)
    }

    modelName := "gemini-1.5-flash-001"
    systemInstruction := "You are an expert analyzing transcripts."

    // Create initial chat with a system instruction.
    chat, err := client.Chats.Create(ctx, modelName, &genai.GenerateContentConfig{
    	SystemInstruction: genai.NewContentFromText(systemInstruction, genai.RoleUser),
    }, nil)
    if err != nil {
    	log.Fatal(err)
    }

    document, err := client.Files.UploadFromPath(
    	ctx, 
    	filepath.Join(getMedia(), "a11.txt"), 
    	&genai.UploadFileConfig{
    		MIMEType : "text/plain",
    	},
    )
    if err != nil {
    	log.Fatal(err)
    }

    // Send first message with the transcript.
    parts := make([]genai.Part, 2)
    parts[0] = genai.Part{Text: "Hi, could you summarize this transcript?"}
    parts[1] = genai.Part{
    	FileData: &genai.FileData{
    		FileURI :      document.URI,
    		MIMEType: document.MIMEType,
    	},
    }

    // Send chat message.
    resp, err := chat.SendMessage(ctx, parts...)
    if err != nil {
    	log.Fatal(err)
    }
    fmt.Println("\n\nmodel: ", resp.Text())

    resp, err = chat.SendMessage(
    	ctx, 
    	genai.Part{
    		Text: "Okay, could you tell me more about the trans-lunar injection",
    	},
    )
    if err != nil {
    	log.Fatal(err)
    }
    fmt.Println("\n\nmodel: ", resp.Text())

    // To cache the conversation so far, pass the chat history as the list of contents.
    cache, err := client.Caches.Create(ctx, modelName, &genai.CreateCachedContentConfig{
    	Contents:          chat.History(false),
    	SystemInstruction: genai.NewContentFromText(systemInstruction, genai.RoleUser),
    })
    if err != nil {
    	log.Fatal(err)
    }

    // Continue the conversation using the cached history.
    chat, err = client.Chats.Create(ctx, modelName, &genai.GenerateContentConfig{
    	CachedContent: cache.Name,
    }, nil)
    if err != nil {
    	log.Fatal(err)
    }

    resp, err = chat.SendMessage(
    	ctx, 
    	genai.Part{
    		Text: "I didn't understand that last part, could you explain it in simpler language?",
    	},
    )
    if err != nil {
    	log.Fatal(err)
    }
    fmt.Println("\n\nmodel: ", resp.Text())  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/go/cache.go#L140-L225

### Response body

If successful, the response body contains a newly created instance of[CachedContent](https://ai.google.dev/api/caching#CachedContent).  

## Method: cachedContents.list

- [Endpoint](https://ai.google.dev/api/caching#body.HTTP_TEMPLATE)
- [Query parameters](https://ai.google.dev/api/caching#body.QUERY_PARAMETERS)
- [Request body](https://ai.google.dev/api/caching#body.request_body)
- [Response body](https://ai.google.dev/api/caching#body.response_body)
  - [JSON representation](https://ai.google.dev/api/caching#body.ListCachedContentsResponse.SCHEMA_REPRESENTATION)

Lists CachedContents.  

### Endpoint

get`https:``/``/generativelanguage.googleapis.com``/v1beta``/cachedContents`  

### Query parameters

`pageSize``integer`  
Optional. The maximum number of cached contents to return. The service may return fewer than this value. If unspecified, some default (under maximum) number of items will be returned. The maximum value is 1000; values above 1000 will be coerced to 1000.
`pageToken``string`  
Optional. A page token, received from a previous`cachedContents.list`call. Provide this to retrieve the subsequent page.

When paginating, all other parameters provided to`cachedContents.list`must match the call that provided the page token.

### Request body

The request body must be empty.  

### Response body

Response with CachedContents list.

If successful, the response body contains data with the following structure:
Fields`cachedContents[]``object (`[CachedContent](https://ai.google.dev/api/caching#CachedContent)`)`  
List of cached contents.
`nextPageToken``string`  
A token, which can be sent as`pageToken`to retrieve the next page. If this field is omitted, there are no subsequent pages.  

|                                                   JSON representation                                                   |
|-------------------------------------------------------------------------------------------------------------------------|
| ``` { "cachedContents": [ { object (https://ai.google.dev/api/caching#CachedContent) } ], "nextPageToken": string } ``` |

## Method: cachedContents.get

- [Endpoint](https://ai.google.dev/api/caching#body.HTTP_TEMPLATE)
- [Path parameters](https://ai.google.dev/api/caching#body.PATH_PARAMETERS)
- [Request body](https://ai.google.dev/api/caching#body.request_body)
- [Response body](https://ai.google.dev/api/caching#body.response_body)
- [Example request](https://ai.google.dev/api/caching#body.codeSnippets)
  - [Basic](https://ai.google.dev/api/caching#body.codeSnippets.group)

Reads CachedContent resource.  

### Endpoint

get`https:``/``/generativelanguage.googleapis.com``/v1beta``/{name=cachedContents``/*}`  

### Path parameters

`name``string`  
Required. The resource name referring to the content cache entry. Format:`cachedContents/{id}`It takes the form`cachedContents/{cachedcontent}`.

### Request body

The request body must be empty.  

### Example request

### Python

    from google import genai

    client = genai.Client()
    document = client.files.upload(file=media / "a11.txt")
    model_name = "gemini-1.5-flash-001"

    cache = client.caches.create(
        model=model_name,
        config={
            "contents": [document],
            "system_instruction": "You are an expert analyzing transcripts.",
        },
    )
    print(client.caches.get(name=cache.name))  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/python/cache.py#L144-L157

### Node.js

    // Make sure to include the following import:
    // import {GoogleGenAI} from '@google/genai';
    const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
    const filePath = path.join(media, "a11.txt");
    const document = await ai.files.upload({
      file: filePath,
      config: { mimeType: "text/plain" },
    });
    console.log("Uploaded file name:", document.name);
    const modelName = "gemini-1.5-flash-001";

    const contents = [
      createUserContent(createPartFromUri(document.uri, document.mimeType)),
    ];

    const cache = await ai.caches.create({
      model: modelName,
      config: {
        contents: contents,
        systemInstruction: "You are an expert analyzing transcripts.",
      },
    });
    const retrievedCache = await ai.caches.get({ name: cache.name });
    console.log("Retrieved Cache:", retrievedCache);  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/javascript/cache.js#L199-L222

### Go

    ctx := context.Background()
    client, err := genai.NewClient(ctx, &genai.ClientConfig{
    	APIKey:  os.Getenv("GEMINI_API_KEY"),
    	Backend: genai.BackendGeminiAPI,
    })
    if err != nil {
    	log.Fatal(err)
    }

    modelName := "gemini-1.5-flash-001"
    document, err := client.Files.UploadFromPath(
    	ctx, 
    	filepath.Join(getMedia(), "a11.txt"), 
    	&genai.UploadFileConfig{
    		MIMEType : "text/plain",
    	},
    )
    if err != nil {
    	log.Fatal(err)
    }
    parts := []*genai.Part{
    	genai.NewPartFromURI(document.URI, document.MIMEType),
    }
    contents := []*genai.Content{
    	genai.NewContentFromParts(parts, genai.RoleUser),
    }

    cache, err := client.Caches.Create(ctx, modelName, &genai.CreateCachedContentConfig{
    	Contents:          contents,
    	SystemInstruction: genai.NewContentFromText(
    		"You are an expert analyzing transcripts.", genai.RoleUser,
    	),
    })
    if err != nil {
    	log.Fatal(err)
    }

    cache, err = client.Caches.Get(ctx, cache.Name, &genai.GetCachedContentConfig{})
    if err != nil {
    	log.Fatal(err)
    }
    fmt.Println("Retrieved cache:")
    fmt.Println(cache)  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/go/cache.go#L285-L327

### Shell

    curl "https://generativelanguage.googleapis.com/v1beta/$CACHE_NAME?key=$GEMINI_API_KEY"  
    https://github.com/google-gemini/deprecated-generative-ai-python/blob/7a7cc5474ddaa0255a4410e05361028a24400abd/samples/rest/cache.sh#L69-L70

### Response body

If successful, the response body contains an instance of[CachedContent](https://ai.google.dev/api/caching#CachedContent).  

## Method: cachedContents.patch

- [Endpoint](https://ai.google.dev/api/caching#body.HTTP_TEMPLATE)
- [Path parameters](https://ai.google.dev/api/caching#body.PATH_PARAMETERS)
- [Query parameters](https://ai.google.dev/api/caching#body.QUERY_PARAMETERS)
- [Request body](https://ai.google.dev/api/caching#body.request_body)
- [Response body](https://ai.google.dev/api/caching#body.response_body)
- [Example request](https://ai.google.dev/api/caching#body.codeSnippets)
  - [Basic](https://ai.google.dev/api/caching#body.codeSnippets.group)

Updates CachedContent resource (only expiration is updatable).  

### Endpoint

patch`https:``/``/generativelanguage.googleapis.com``/v1beta``/{cachedContent.name=cachedContents``/*}`  
`PATCH https://generativelanguage.googleapis.com/v1beta/{cachedContent.name=cachedContents/*}`

### Path parameters

`cachedContent.name``string`  
Output only. Identifier. The resource name referring to the cached content. Format:`cachedContents/{id}`It takes the form`cachedContents/{cachedcontent}`.

### Query parameters

`updateMask``string (`[FieldMask](https://protobuf.dev/reference/protobuf/google.protobuf/#field-mask)` format)`  
The list of fields to update.

This is a comma-separated list of fully qualified names of fields. Example:`"user.displayName,photo"`.

### Request body

The request body contains an instance of[CachedContent](https://ai.google.dev/api/caching#CachedContent).
Fields  
`expiration``Union type`  
Specifies when this resource will expire.`expiration`can be only one of the following:
`expireTime``string (`[Timestamp](https://protobuf.dev/reference/protobuf/google.protobuf/#timestamp)` format)`  
Timestamp in UTC of when this resource is considered expired. This is*always*provided on output, regardless of what was sent on input.

Uses RFC 3339, where generated output will always be Z-normalized and use 0, 3, 6 or 9 fractional digits. Offsets other than "Z" are also accepted. Examples:`"2014-10-02T15:01:23Z"`,`"2014-10-02T15:01:23.045123456Z"`or`"2014-10-02T15:01:23+05:30"`.
`ttl``string (`[Duration](https://protobuf.dev/reference/protobuf/google.protobuf/#duration)` format)`  
Input only. New TTL for this resource, input only.

A duration in seconds with up to nine fractional digits, ending with '`s`'. Example:`"3.5s"`.  

### Example request

### Python

    from google import genai
    from google.genai import types
    import datetime

    client = genai.Client()
    document = client.files.upload(file=media / "a11.txt")
    model_name = "gemini-1.5-flash-001"

    cache = client.caches.create(
        model=model_name,
        config={
            "contents": [document],
            "system_instruction": "You are an expert analyzing transcripts.",
        },
    )

    # Update the cache's time-to-live (ttl)
    ttl = f"{int(datetime.timedelta(hours=2).total_seconds())}s"
    client.caches.update(
        name=cache.name, config=types.UpdateCachedContentConfig(ttl=ttl)
    )
    print(f"After update:\n {cache}")

    # Alternatively, update the expire_time directly
    # Update the expire_time directly in valid RFC 3339 format (UTC with a "Z" suffix)
    expire_time = (
        (
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(minutes=15)
        )
        .isoformat()
        .replace("+00:00", "Z")
    )
    client.caches.update(
        name=cache.name,
        config=types.UpdateCachedContentConfig(expire_time=expire_time),
    )  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/python/cache.py#L184-L220

### Node.js

    // Make sure to include the following import:
    // import {GoogleGenAI} from '@google/genai';
    const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
    const filePath = path.join(media, "a11.txt");
    const document = await ai.files.upload({
      file: filePath,
      config: { mimeType: "text/plain" },
    });
    console.log("Uploaded file name:", document.name);
    const modelName = "gemini-1.5-flash-001";

    const contents = [
      createUserContent(createPartFromUri(document.uri, document.mimeType)),
    ];

    let cache = await ai.caches.create({
      model: modelName,
      config: {
        contents: contents,
        systemInstruction: "You are an expert analyzing transcripts.",
      },
    });

    // Update the cache's time-to-live (ttl)
    const ttl = `${2 * 3600}s`; // 2 hours in seconds
    cache = await ai.caches.update({
      name: cache.name,
      config: { ttl },
    });
    console.log("After update (TTL):", cache);

    // Alternatively, update the expire_time directly (in RFC 3339 format with a "Z" suffix)
    const expireTime = new Date(Date.now() + 15 * 60000)
      .toISOString()
      .replace(/\.\d{3}Z$/, "Z");
    cache = await ai.caches.update({
      name: cache.name,
      config: { expireTime: expireTime },
    });
    console.log("After update (expire_time):", cache);  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/javascript/cache.js#L272-L311

### Go

    ctx := context.Background()
    client, err := genai.NewClient(ctx, &genai.ClientConfig{
    	APIKey:  os.Getenv("GEMINI_API_KEY"),
    	Backend: genai.BackendGeminiAPI,
    })
    if err != nil {
    	log.Fatal(err)
    }

    modelName := "gemini-1.5-flash-001"
    document, err := client.Files.UploadFromPath(
    	ctx, 
    	filepath.Join(getMedia(), "a11.txt"), 
    	&genai.UploadFileConfig{
    		MIMEType : "text/plain",
    	},
    )
    if err != nil {
    	log.Fatal(err)
    }
    parts := []*genai.Part{
    	genai.NewPartFromURI(document.URI, document.MIMEType),
    }
    contents := []*genai.Content{
    	genai.NewContentFromParts(parts, genai.RoleUser),
    }

    cache, err := client.Caches.Create(ctx, modelName, &genai.CreateCachedContentConfig{
    	Contents:          contents,
    	SystemInstruction: genai.NewContentFromText(
    		"You are an expert analyzing transcripts.", genai.RoleUser,
    	),
    })
    if err != nil {
    	log.Fatal(err)
    }

    _, err = client.Caches.Delete(ctx, cache.Name, &genai.DeleteCachedContentConfig{})
    if err != nil {
    	log.Fatal(err)
    }
    fmt.Println("Cache deleted:", cache.Name)  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/go/cache.go#L237-L278

### Shell

    curl -X PATCH "https://generativelanguage.googleapis.com/v1beta/$CACHE_NAME?key=$GEMINI_API_KEY" \
     -H 'Content-Type: application/json' \
     -d '{"ttl": "600s"}'  
    https://github.com/google-gemini/deprecated-generative-ai-python/blob/7a7cc5474ddaa0255a4410e05361028a24400abd/samples/rest/cache.sh#L74-L77

### Response body

If successful, the response body contains an instance of[CachedContent](https://ai.google.dev/api/caching#CachedContent).  

## Method: cachedContents.delete

- [Endpoint](https://ai.google.dev/api/caching#body.HTTP_TEMPLATE)
- [Path parameters](https://ai.google.dev/api/caching#body.PATH_PARAMETERS)
- [Request body](https://ai.google.dev/api/caching#body.request_body)
- [Response body](https://ai.google.dev/api/caching#body.response_body)
- [Example request](https://ai.google.dev/api/caching#body.codeSnippets)
  - [Basic](https://ai.google.dev/api/caching#body.codeSnippets.group)

Deletes CachedContent resource.  

### Endpoint

delete`https:``/``/generativelanguage.googleapis.com``/v1beta``/{name=cachedContents``/*}`  

### Path parameters

`name``string`  
Required. The resource name referring to the content cache entry Format:`cachedContents/{id}`It takes the form`cachedContents/{cachedcontent}`.

### Request body

The request body must be empty.  

### Example request

### Python

    from google import genai

    client = genai.Client()
    document = client.files.upload(file=media / "a11.txt")
    model_name = "gemini-1.5-flash-001"

    cache = client.caches.create(
        model=model_name,
        config={
            "contents": [document],
            "system_instruction": "You are an expert analyzing transcripts.",
        },
    )
    client.caches.delete(name=cache.name)  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/python/cache.py#L126-L139

### Node.js

    // Make sure to include the following import:
    // import {GoogleGenAI} from '@google/genai';
    const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
    const filePath = path.join(media, "a11.txt");
    const document = await ai.files.upload({
      file: filePath,
      config: { mimeType: "text/plain" },
    });
    console.log("Uploaded file name:", document.name);
    const modelName = "gemini-1.5-flash-001";

    const contents = [
      createUserContent(createPartFromUri(document.uri, document.mimeType)),
    ];

    const cache = await ai.caches.create({
      model: modelName,
      config: {
        contents: contents,
        systemInstruction: "You are an expert analyzing transcripts.",
      },
    });
    await ai.caches.delete({ name: cache.name });
    console.log("Cache deleted:", cache.name);  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/javascript/cache.js#L170-L193

### Go

    ctx := context.Background()
    client, err := genai.NewClient(ctx, &genai.ClientConfig{
    	APIKey:  os.Getenv("GEMINI_API_KEY"),
    	Backend: genai.BackendGeminiAPI,
    })
    if err != nil {
    	log.Fatal(err)
    }

    modelName := "gemini-1.5-flash-001"
    document, err := client.Files.UploadFromPath(
    	ctx, 
    	filepath.Join(getMedia(), "a11.txt"), 
    	&genai.UploadFileConfig{
    		MIMEType : "text/plain",
    	},
    )
    if err != nil {
    	log.Fatal(err)
    }
    parts := []*genai.Part{
    	genai.NewPartFromURI(document.URI, document.MIMEType),
    }
    contents := []*genai.Content{
    	genai.NewContentFromParts(parts, genai.RoleUser),
    }

    cache, err := client.Caches.Create(ctx, modelName, &genai.CreateCachedContentConfig{
    	Contents:          contents,
    	SystemInstruction: genai.NewContentFromText(
    		"You are an expert analyzing transcripts.", genai.RoleUser,
    	),
    })
    if err != nil {
    	log.Fatal(err)
    }

    _, err = client.Caches.Delete(ctx, cache.Name, &genai.DeleteCachedContentConfig{})
    if err != nil {
    	log.Fatal(err)
    }
    fmt.Println("Cache deleted:", cache.Name)  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/go/cache.go#L237-L278

### Shell

    curl -X DELETE "https://generativelanguage.googleapis.com/v1beta/$CACHE_NAME?key=$GEMINI_API_KEY"  
    https://github.com/google-gemini/deprecated-generative-ai-python/blob/7a7cc5474ddaa0255a4410e05361028a24400abd/samples/rest/cache.sh#L81-L82

### Response body

If successful, the response body is an empty JSON object.  

## REST Resource: cachedContents

- [Resource: CachedContent](https://ai.google.dev/api/caching#CachedContent)
  - [JSON representation](https://ai.google.dev/api/caching#CachedContent.SCHEMA_REPRESENTATION)
- [Content](https://ai.google.dev/api/caching#Content)
  - [JSON representation](https://ai.google.dev/api/caching#Content.SCHEMA_REPRESENTATION)
- [Part](https://ai.google.dev/api/caching#Part)
  - [JSON representation](https://ai.google.dev/api/caching#Part.SCHEMA_REPRESENTATION)
- [Blob](https://ai.google.dev/api/caching#Blob)
  - [JSON representation](https://ai.google.dev/api/caching#Blob.SCHEMA_REPRESENTATION)
- [FunctionCall](https://ai.google.dev/api/caching#FunctionCall)
  - [JSON representation](https://ai.google.dev/api/caching#FunctionCall.SCHEMA_REPRESENTATION)
- [FunctionResponse](https://ai.google.dev/api/caching#FunctionResponse)
  - [JSON representation](https://ai.google.dev/api/caching#FunctionResponse.SCHEMA_REPRESENTATION)
- [FunctionResponsePart](https://ai.google.dev/api/caching#FunctionResponsePart)
  - [JSON representation](https://ai.google.dev/api/caching#FunctionResponsePart.SCHEMA_REPRESENTATION)
- [FunctionResponseBlob](https://ai.google.dev/api/caching#FunctionResponseBlob)
  - [JSON representation](https://ai.google.dev/api/caching#FunctionResponseBlob.SCHEMA_REPRESENTATION)
- [Scheduling](https://ai.google.dev/api/caching#Scheduling)
- [FileData](https://ai.google.dev/api/caching#FileData)
  - [JSON representation](https://ai.google.dev/api/caching#FileData.SCHEMA_REPRESENTATION)
- [ExecutableCode](https://ai.google.dev/api/caching#ExecutableCode)
  - [JSON representation](https://ai.google.dev/api/caching#ExecutableCode.SCHEMA_REPRESENTATION)
- [Language](https://ai.google.dev/api/caching#Language)
- [CodeExecutionResult](https://ai.google.dev/api/caching#CodeExecutionResult)
  - [JSON representation](https://ai.google.dev/api/caching#CodeExecutionResult.SCHEMA_REPRESENTATION)
- [Outcome](https://ai.google.dev/api/caching#Outcome)
- [VideoMetadata](https://ai.google.dev/api/caching#VideoMetadata)
  - [JSON representation](https://ai.google.dev/api/caching#VideoMetadata.SCHEMA_REPRESENTATION)
- [Tool](https://ai.google.dev/api/caching#Tool)
  - [JSON representation](https://ai.google.dev/api/caching#Tool.SCHEMA_REPRESENTATION)
- [FunctionDeclaration](https://ai.google.dev/api/caching#FunctionDeclaration)
  - [JSON representation](https://ai.google.dev/api/caching#FunctionDeclaration.SCHEMA_REPRESENTATION)
- [Schema](https://ai.google.dev/api/caching#Schema)
  - [JSON representation](https://ai.google.dev/api/caching#Schema.SCHEMA_REPRESENTATION)
- [Type](https://ai.google.dev/api/caching#Type)
- [Behavior](https://ai.google.dev/api/caching#Behavior)
- [GoogleSearchRetrieval](https://ai.google.dev/api/caching#GoogleSearchRetrieval)
  - [JSON representation](https://ai.google.dev/api/caching#GoogleSearchRetrieval.SCHEMA_REPRESENTATION)
- [DynamicRetrievalConfig](https://ai.google.dev/api/caching#DynamicRetrievalConfig)
  - [JSON representation](https://ai.google.dev/api/caching#DynamicRetrievalConfig.SCHEMA_REPRESENTATION)
- [Mode](https://ai.google.dev/api/caching#Mode)
- [CodeExecution](https://ai.google.dev/api/caching#CodeExecution)
- [GoogleSearch](https://ai.google.dev/api/caching#GoogleSearch)
  - [JSON representation](https://ai.google.dev/api/caching#GoogleSearch.SCHEMA_REPRESENTATION)
- [Interval](https://ai.google.dev/api/caching#Interval)
  - [JSON representation](https://ai.google.dev/api/caching#Interval.SCHEMA_REPRESENTATION)
- [ComputerUse](https://ai.google.dev/api/caching#ComputerUse)
  - [JSON representation](https://ai.google.dev/api/caching#ComputerUse.SCHEMA_REPRESENTATION)
- [Environment](https://ai.google.dev/api/caching#Environment)
- [UrlContext](https://ai.google.dev/api/caching#UrlContext)
- [FileSearch](https://ai.google.dev/api/caching#FileSearch)
  - [JSON representation](https://ai.google.dev/api/caching#FileSearch.SCHEMA_REPRESENTATION)
- [GoogleMaps](https://ai.google.dev/api/caching#GoogleMaps)
  - [JSON representation](https://ai.google.dev/api/caching#GoogleMaps.SCHEMA_REPRESENTATION)
- [ToolConfig](https://ai.google.dev/api/caching#ToolConfig)
  - [JSON representation](https://ai.google.dev/api/caching#ToolConfig.SCHEMA_REPRESENTATION)
- [FunctionCallingConfig](https://ai.google.dev/api/caching#FunctionCallingConfig)
  - [JSON representation](https://ai.google.dev/api/caching#FunctionCallingConfig.SCHEMA_REPRESENTATION)
- [Mode](https://ai.google.dev/api/caching#Mode_1)
- [RetrievalConfig](https://ai.google.dev/api/caching#RetrievalConfig)
  - [JSON representation](https://ai.google.dev/api/caching#RetrievalConfig.SCHEMA_REPRESENTATION)
- [LatLng](https://ai.google.dev/api/caching#LatLng)
  - [JSON representation](https://ai.google.dev/api/caching#LatLng.SCHEMA_REPRESENTATION)
- [UsageMetadata](https://ai.google.dev/api/caching#UsageMetadata)
  - [JSON representation](https://ai.google.dev/api/caching#UsageMetadata.SCHEMA_REPRESENTATION)
- [Methods](https://ai.google.dev/api/caching#METHODS_SUMMARY)

## Resource: CachedContent

Content that has been preprocessed and can be used in subsequent request to GenerativeService.

Cached content can be only used with model it was created for.
Fields`contents[]``object (`[Content](https://ai.google.dev/api/caching#Content)`)`  
Optional. Input only. Immutable. The content to cache.
`tools[]``object (`[Tool](https://ai.google.dev/api/caching#Tool)`)`  
Optional. Input only. Immutable. A list of`Tools`the model may use to generate the next response
`createTime``string (`[Timestamp](https://protobuf.dev/reference/protobuf/google.protobuf/#timestamp)` format)`  
Output only. Creation time of the cache entry.

Uses RFC 3339, where generated output will always be Z-normalized and use 0, 3, 6 or 9 fractional digits. Offsets other than "Z" are also accepted. Examples:`"2014-10-02T15:01:23Z"`,`"2014-10-02T15:01:23.045123456Z"`or`"2014-10-02T15:01:23+05:30"`.
`updateTime``string (`[Timestamp](https://protobuf.dev/reference/protobuf/google.protobuf/#timestamp)` format)`  
Output only. When the cache entry was last updated in UTC time.

Uses RFC 3339, where generated output will always be Z-normalized and use 0, 3, 6 or 9 fractional digits. Offsets other than "Z" are also accepted. Examples:`"2014-10-02T15:01:23Z"`,`"2014-10-02T15:01:23.045123456Z"`or`"2014-10-02T15:01:23+05:30"`.
`usageMetadata``object (`[UsageMetadata](https://ai.google.dev/api/caching#UsageMetadata)`)`  
Output only. Metadata on the usage of the cached content.  
`expiration``Union type`  
Specifies when this resource will expire.`expiration`can be only one of the following:
`expireTime``string (`[Timestamp](https://protobuf.dev/reference/protobuf/google.protobuf/#timestamp)` format)`  
Timestamp in UTC of when this resource is considered expired. This is*always*provided on output, regardless of what was sent on input.

Uses RFC 3339, where generated output will always be Z-normalized and use 0, 3, 6 or 9 fractional digits. Offsets other than "Z" are also accepted. Examples:`"2014-10-02T15:01:23Z"`,`"2014-10-02T15:01:23.045123456Z"`or`"2014-10-02T15:01:23+05:30"`.
`ttl``string (`[Duration](https://protobuf.dev/reference/protobuf/google.protobuf/#duration)` format)`  
Input only. New TTL for this resource, input only.

A duration in seconds with up to nine fractional digits, ending with '`s`'. Example:`"3.5s"`.
`name``string`  
Output only. Identifier. The resource name referring to the cached content. Format:`cachedContents/{id}`
`displayName``string`  
Optional. Immutable. The user-generated meaningful display name of the cached content. Maximum 128 Unicode characters.
`model``string`  
Required. Immutable. The name of the`Model`to use for cached content Format:`models/{model}`
`systemInstruction``object (`[Content](https://ai.google.dev/api/caching#Content)`)`  
Optional. Input only. Immutable. Developer set system instruction. Currently text only.
`toolConfig``object (`[ToolConfig](https://ai.google.dev/api/caching#ToolConfig)`)`  
Optional. Input only. Immutable. Tool config. This config is shared for all tools.  

|                                                                                                                                                                                                                                                                      JSON representation                                                                                                                                                                                                                                                                      |
|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ``` { "contents": [ { object (https://ai.google.dev/api/caching#Content) } ], "tools": [ { object (https://ai.google.dev/api/caching#Tool) } ], "createTime": string, "updateTime": string, "usageMetadata": { object (https://ai.google.dev/api/caching#UsageMetadata) }, // expiration "expireTime": string, "ttl": string // Union type "name": string, "displayName": string, "model": string, "systemInstruction": { object (https://ai.google.dev/api/caching#Content) }, "toolConfig": { object (https://ai.google.dev/api/caching#ToolConfig) } } ``` |

## Content

The base structured datatype containing multi-part content of a message.

A`Content`includes a`role`field designating the producer of the`Content`and a`parts`field containing multi-part data that contains the content of the message turn.
Fields`parts[]``object (`[Part](https://ai.google.dev/api/caching#Part)`)`  
Ordered`Parts`that constitute a single message. Parts may have different MIME types.
`role``string`  
Optional. The producer of the content. Must be either 'user' or 'model'.

Useful to set for multi-turn conversations, otherwise can be left blank or unset.  

|                                     JSON representation                                      |
|----------------------------------------------------------------------------------------------|
| ``` { "parts": [ { object (https://ai.google.dev/api/caching#Part) } ], "role": string } ``` |

## Part

A datatype containing media that is part of a multi-part`Content`message.

A`Part`consists of data which has an associated datatype. A`Part`can only contain one of the accepted types in`Part.data`.

A`Part`must have a fixed IANA MIME type identifying the type and subtype of the media if the`inlineData`field is filled with raw bytes.
Fields`thought``boolean`  
Optional. Indicates if the part is thought from the model.
`thoughtSignature``string (`[bytes](https://developers.google.com/discovery/v1/type-format)` format)`  
Optional. An opaque signature for the thought so it can be reused in subsequent requests.

A base64-encoded string.
`partMetadata``object (`[Struct](https://protobuf.dev/reference/protobuf/google.protobuf/#struct)` format)`  
Custom metadata associated with the Part. Agents using genai.Part as content representation may need to keep track of the additional information. For example it can be name of a file/source from which the Part originates or a way to multiplex multiple Part streams.  
`data``Union type`  
`data`can be only one of the following:
`text``string`  
Inline text.
`inlineData``object (`[Blob](https://ai.google.dev/api/caching#Blob)`)`  
Inline media bytes.
`functionCall``object (`[FunctionCall](https://ai.google.dev/api/caching#FunctionCall)`)`  
A predicted`FunctionCall`returned from the model that contains a string representing the`FunctionDeclaration.name`with the arguments and their values.
`functionResponse``object (`[FunctionResponse](https://ai.google.dev/api/caching#FunctionResponse)`)`  
The result output of a`FunctionCall`that contains a string representing the`FunctionDeclaration.name`and a structured JSON object containing any output from the function is used as context to the model.
`fileData``object (`[FileData](https://ai.google.dev/api/caching#FileData)`)`  
URI based data.
`executableCode``object (`[ExecutableCode](https://ai.google.dev/api/caching#ExecutableCode)`)`  
Code generated by the model that is meant to be executed.
`codeExecutionResult``object (`[CodeExecutionResult](https://ai.google.dev/api/caching#CodeExecutionResult)`)`  
Result of executing the`ExecutableCode`.  
`metadata``Union type`  
Controls extra preprocessing of data.`metadata`can be only one of the following:
`videoMetadata``object (`[VideoMetadata](https://ai.google.dev/api/caching#VideoMetadata)`)`  
Optional. Video metadata. The metadata should only be specified while the video data is presented in inlineData or fileData.  

|                                                                                                                                                                                                                                                                                                                                                    JSON representation                                                                                                                                                                                                                                                                                                                                                     |
|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ``` { "thought": boolean, "thoughtSignature": string, "partMetadata": { object }, // data "text": string, "inlineData": { object (https://ai.google.dev/api/caching#Blob) }, "functionCall": { object (https://ai.google.dev/api/caching#FunctionCall) }, "functionResponse": { object (https://ai.google.dev/api/caching#FunctionResponse) }, "fileData": { object (https://ai.google.dev/api/caching#FileData) }, "executableCode": { object (https://ai.google.dev/api/caching#ExecutableCode) }, "codeExecutionResult": { object (https://ai.google.dev/api/caching#CodeExecutionResult) } // Union type // metadata "videoMetadata": { object (https://ai.google.dev/api/caching#VideoMetadata) } // Union type } ``` |

## Blob

Raw media bytes.

Text should not be sent as raw bytes, use the 'text' field.
Fields`mimeType``string`  
The IANA standard MIME type of the source data. Examples: - image/png - image/jpeg If an unsupported MIME type is provided, an error will be returned. For a complete list of supported types, see[Supported file formats](https://ai.google.dev/gemini-api/docs/prompting_with_media#supported_file_formats).
`data``string (`[bytes](https://developers.google.com/discovery/v1/type-format)` format)`  
Raw bytes for media formats.

A base64-encoded string.  

|              JSON representation               |
|------------------------------------------------|
| ``` { "mimeType": string, "data": string } ``` |

## FunctionCall

A predicted`FunctionCall`returned from the model that contains a string representing the`FunctionDeclaration.name`with the arguments and their values.
Fields`id``string`  
Optional. The unique id of the function call. If populated, the client to execute the`functionCall`and return the response with the matching`id`.
`name``string`  
Required. The name of the function to call. Must be a-z, A-Z, 0-9, or contain underscores and dashes, with a maximum length of 64.
`args``object (`[Struct](https://protobuf.dev/reference/protobuf/google.protobuf/#struct)` format)`  
Optional. The function parameters and values in JSON object format.  

|                     JSON representation                      |
|--------------------------------------------------------------|
| ``` { "id": string, "name": string, "args": { object } } ``` |

## FunctionResponse

The result output from a`FunctionCall`that contains a string representing the`FunctionDeclaration.name`and a structured JSON object containing any output from the function is used as context to the model. This should contain the result of a`FunctionCall`made based on model prediction.
Fields`id``string`  
Optional. The id of the function call this response is for. Populated by the client to match the corresponding function call`id`.
`name``string`  
Required. The name of the function to call. Must be a-z, A-Z, 0-9, or contain underscores and dashes, with a maximum length of 64.
`response``object (`[Struct](https://protobuf.dev/reference/protobuf/google.protobuf/#struct)` format)`  
Required. The function response in JSON object format. Callers can use any keys of their choice that fit the function's syntax to return the function output, e.g. "output", "result", etc. In particular, if the function call failed to execute, the response can have an "error" key to return error details to the model.
`parts[]``object (`[FunctionResponsePart](https://ai.google.dev/api/caching#FunctionResponsePart)`)`  
Optional. Ordered`Parts`that constitute a function response. Parts may have different IANA MIME types.
`willContinue``boolean`  
Optional. Signals that function call continues, and more responses will be returned, turning the function call into a generator. Is only applicable to NON_BLOCKING function calls, is ignored otherwise. If set to false, future responses will not be considered. It is allowed to return empty`response`with`willContinue=False`to signal that the function call is finished. This may still trigger the model generation. To avoid triggering the generation and finish the function call, additionally set`scheduling`to`SILENT`.
`scheduling``enum (`[Scheduling](https://ai.google.dev/api/caching#Scheduling)`)`  
Optional. Specifies how the response should be scheduled in the conversation. Only applicable to NON_BLOCKING function calls, is ignored otherwise. Defaults to WHEN_IDLE.  

|                                                                                                              JSON representation                                                                                                               |
|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ``` { "id": string, "name": string, "response": { object }, "parts": [ { object (https://ai.google.dev/api/caching#FunctionResponsePart) } ], "willContinue": boolean, "scheduling": enum (https://ai.google.dev/api/caching#Scheduling) } ``` |

## FunctionResponsePart

A datatype containing media that is part of a`FunctionResponse`message.

A`FunctionResponsePart`consists of data which has an associated datatype. A`FunctionResponsePart`can only contain one of the accepted types in`FunctionResponsePart.data`.

A`FunctionResponsePart`must have a fixed IANA MIME type identifying the type and subtype of the media if the`inlineData`field is filled with raw bytes.
Fields  
`data``Union type`  
The data of the function response part.`data`can be only one of the following:
`inlineData``object (`[FunctionResponseBlob](https://ai.google.dev/api/caching#FunctionResponseBlob)`)`  
Inline media bytes.  

|                                                 JSON representation                                                 |
|---------------------------------------------------------------------------------------------------------------------|
| ``` { // data "inlineData": { object (https://ai.google.dev/api/caching#FunctionResponseBlob) } // Union type } ``` |

## FunctionResponseBlob

Raw media bytes for function response.

Text should not be sent as raw bytes, use the 'FunctionResponse.response' field.
Fields`mimeType``string`  
The IANA standard MIME type of the source data. Examples: - image/png - image/jpeg If an unsupported MIME type is provided, an error will be returned. For a complete list of supported types, see[Supported file formats](https://ai.google.dev/gemini-api/docs/prompting_with_media#supported_file_formats).
`data``string (`[bytes](https://developers.google.com/discovery/v1/type-format)` format)`  
Raw bytes for media formats.

A base64-encoded string.  

|              JSON representation               |
|------------------------------------------------|
| ``` { "mimeType": string, "data": string } ``` |

## Scheduling

Specifies how the response should be scheduled in the conversation.

|                                                                    Enums                                                                     ||
|--------------------------|--------------------------------------------------------------------------------------------------------------------|
| `SCHEDULING_UNSPECIFIED` | This value is unused.                                                                                              |
| `SILENT`                 | Only add the result to the conversation context, do not interrupt or trigger generation.                           |
| `WHEN_IDLE`              | Add the result to the conversation context, and prompt to generate output without interrupting ongoing generation. |
| `INTERRUPT`              | Add the result to the conversation context, interrupt ongoing generation and prompt to generate output.            |

## FileData

URI based data.
Fields`mimeType``string`  
Optional. The IANA standard MIME type of the source data.
`fileUri``string`  
Required. URI.  

|                JSON representation                |
|---------------------------------------------------|
| ``` { "mimeType": string, "fileUri": string } ``` |

## ExecutableCode

Code generated by the model that is meant to be executed, and the result returned to the model.

Only generated when using the`CodeExecution`tool, in which the code will be automatically executed, and a corresponding`CodeExecutionResult`will also be generated.
Fields`language``enum (`[Language](https://ai.google.dev/api/caching#Language)`)`  
Required. Programming language of the`code`.
`code``string`  
Required. The code to be executed.  

|                                    JSON representation                                    |
|-------------------------------------------------------------------------------------------|
| ``` { "language": enum (https://ai.google.dev/api/caching#Language), "code": string } ``` |

## Language

Supported programming languages for the generated code.

|                                                  Enums                                                   ||
|------------------------|----------------------------------------------------------------------------------|
| `LANGUAGE_UNSPECIFIED` | Unspecified language. This value should not be used.                             |
| `PYTHON`               | Python \>= 3.10, with numpy and simpy available. Python is the default language. |

## CodeExecutionResult

Result of executing the`ExecutableCode`.

Only generated when using the`CodeExecution`, and always follows a`part`containing the`ExecutableCode`.
Fields`outcome``enum (`[Outcome](https://ai.google.dev/api/caching#Outcome)`)`  
Required. Outcome of the code execution.
`output``string`  
Optional. Contains stdout when code execution is successful, stderr or other description otherwise.  

|                                    JSON representation                                    |
|-------------------------------------------------------------------------------------------|
| ``` { "outcome": enum (https://ai.google.dev/api/caching#Outcome), "output": string } ``` |

## Outcome

Enumeration of possible outcomes of the code execution.

|                                                               Enums                                                                ||
|-----------------------------|-------------------------------------------------------------------------------------------------------|
| `OUTCOME_UNSPECIFIED`       | Unspecified status. This value should not be used.                                                    |
| `OUTCOME_OK`                | Code execution completed successfully.                                                                |
| `OUTCOME_FAILED`            | Code execution finished but with a failure.`stderr`should contain the reason.                         |
| `OUTCOME_DEADLINE_EXCEEDED` | Code execution ran for too long, and was cancelled. There may or may not be a partial output present. |

## VideoMetadata

Metadata describes the input video content.
Fields`startOffset``string (`[Duration](https://protobuf.dev/reference/protobuf/google.protobuf/#duration)` format)`  
Optional. The start offset of the video.

A duration in seconds with up to nine fractional digits, ending with '`s`'. Example:`"3.5s"`.
`endOffset``string (`[Duration](https://protobuf.dev/reference/protobuf/google.protobuf/#duration)` format)`  
Optional. The end offset of the video.

A duration in seconds with up to nine fractional digits, ending with '`s`'. Example:`"3.5s"`.
`fps``number`  
Optional. The frame rate of the video sent to the model. If not specified, the default value will be 1.0. The fps range is (0.0, 24.0\].  

|                          JSON representation                          |
|-----------------------------------------------------------------------|
| ``` { "startOffset": string, "endOffset": string, "fps": number } ``` |

## Tool

Tool details that the model may use to generate response.

A`Tool`is a piece of code that enables the system to interact with external systems to perform an action, or set of actions, outside of knowledge and scope of the model.

Next ID: 13
Fields`functionDeclarations[]``object (`[FunctionDeclaration](https://ai.google.dev/api/caching#FunctionDeclaration)`)`  
Optional. A list of`FunctionDeclarations`available to the model that can be used for function calling.

The model or system does not execute the function. Instead the defined function may be returned as a[FunctionCall](https://ai.google.dev/api/caching#Part.FIELDS.function_call)with arguments to the client side for execution. The model may decide to call a subset of these functions by populating[FunctionCall](https://ai.google.dev/api/caching#Part.FIELDS.function_call)in the response. The next conversation turn may contain a[FunctionResponse](https://ai.google.dev/api/caching#Part.FIELDS.function_response)with the[Content.role](https://ai.google.dev/api/caching#Content.FIELDS.role)"function" generation context for the next model turn.
`googleSearchRetrieval``object (`[GoogleSearchRetrieval](https://ai.google.dev/api/caching#GoogleSearchRetrieval)`)`  
Optional. Retrieval tool that is powered by Google search.
`codeExecution``object (`[CodeExecution](https://ai.google.dev/api/caching#CodeExecution)`)`  
Optional. Enables the model to execute code as part of generation.
`googleSearch``object (`[GoogleSearch](https://ai.google.dev/api/caching#GoogleSearch)`)`  
Optional. GoogleSearch tool type. Tool to support Google Search in Model. Powered by Google.
`computerUse``object (`[ComputerUse](https://ai.google.dev/api/caching#ComputerUse)`)`  
Optional. Tool to support the model interacting directly with the computer. If enabled, it automatically populates computer-use specific Function Declarations.
`urlContext``object (`[UrlContext](https://ai.google.dev/api/caching#UrlContext)`)`  
Optional. Tool to support URL context retrieval.
`fileSearch``object (`[FileSearch](https://ai.google.dev/api/caching#FileSearch)`)`  
Optional. FileSearch tool type. Tool to retrieve knowledge from Semantic Retrieval corpora.
`googleMaps``object (`[GoogleMaps](https://ai.google.dev/api/caching#GoogleMaps)`)`  
Optional. Tool that allows grounding the model's response with geospatial context related to the user's query.  

|                                                                                                                                                                                                                                                                                                                             JSON representation                                                                                                                                                                                                                                                                                                                             |
|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ``` { "functionDeclarations": [ { object (https://ai.google.dev/api/caching#FunctionDeclaration) } ], "googleSearchRetrieval": { object (https://ai.google.dev/api/caching#GoogleSearchRetrieval) }, "codeExecution": { object (https://ai.google.dev/api/caching#CodeExecution) }, "googleSearch": { object (https://ai.google.dev/api/caching#GoogleSearch) }, "computerUse": { object (https://ai.google.dev/api/caching#ComputerUse) }, "urlContext": { object (https://ai.google.dev/api/caching#UrlContext) }, "fileSearch": { object (https://ai.google.dev/api/caching#FileSearch) }, "googleMaps": { object (https://ai.google.dev/api/caching#GoogleMaps) } } ``` |

## FunctionDeclaration

Structured representation of a function declaration as defined by the[OpenAPI 3.03 specification](https://spec.openapis.org/oas/v3.0.3). Included in this declaration are the function name and parameters. This FunctionDeclaration is a representation of a block of code that can be used as a`Tool`by the model and executed by the client.
Fields`name``string`  
Required. The name of the function. Must be a-z, A-Z, 0-9, or contain underscores, colons, dots, and dashes, with a maximum length of 64.
`description``string`  
Required. A brief description of the function.
`behavior``enum (`[Behavior](https://ai.google.dev/api/caching#Behavior)`)`  
Optional. Specifies the function Behavior. Currently only supported by the BidiGenerateContent method.
`parameters``object (`[Schema](https://ai.google.dev/api/caching#Schema)`)`  
Optional. Describes the parameters to this function. Reflects the Open API 3.03 Parameter Object string Key: the name of the parameter. Parameter names are case sensitive. Schema Value: the Schema defining the type used for the parameter.
`parametersJsonSchema``value (`[Value](https://protobuf.dev/reference/protobuf/google.protobuf/#value)` format)`  
Optional. Describes the parameters to the function in JSON Schema format. The schema must describe an object where the properties are the parameters to the function. For example:  

    {
      "type": "object",
      "properties": {
        "name": { "type": "string" },
        "age": { "type": "integer" }
      },
      "additionalProperties": false,
      "required": ["name", "age"],
      "propertyOrdering": ["name", "age"]
    }

This field is mutually exclusive with`parameters`.
`response``object (`[Schema](https://ai.google.dev/api/caching#Schema)`)`  
Optional. Describes the output from this function in JSON Schema format. Reflects the Open API 3.03 Response Object. The Schema defines the type used for the response value of the function.
`responseJsonSchema``value (`[Value](https://protobuf.dev/reference/protobuf/google.protobuf/#value)` format)`  
Optional. Describes the output from this function in JSON Schema format. The value specified by the schema is the response value of the function.

This field is mutually exclusive with`response`.  

|                                                                                                                                                 JSON representation                                                                                                                                                  |
|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ``` { "name": string, "description": string, "behavior": enum (https://ai.google.dev/api/caching#Behavior), "parameters": { object (https://ai.google.dev/api/caching#Schema) }, "parametersJsonSchema": value, "response": { object (https://ai.google.dev/api/caching#Schema) }, "responseJsonSchema": value } ``` |

## Schema

The`Schema`object allows the definition of input and output data types. These types can be objects, but also primitives and arrays. Represents a select subset of an[OpenAPI 3.0 schema object](https://spec.openapis.org/oas/v3.0.3#schema).
Fields`type``enum (`[Type](https://ai.google.dev/api/caching#Type)`)`  
Required. Data type.
`format``string`  
Optional. The format of the data. Any value is allowed, but most do not trigger any special functionality.
`title``string`  
Optional. The title of the schema.
`description``string`  
Optional. A brief description of the parameter. This could contain examples of use. Parameter description may be formatted as Markdown.
`nullable``boolean`  
Optional. Indicates if the value may be null.
`enum[]``string`  
Optional. Possible values of the element of Type.STRING with enum format. For example we can define an Enum Direction as : {type:STRING, format:enum, enum:\["EAST", NORTH", "SOUTH", "WEST"\]}
`maxItems``string (`[int64](https://developers.google.com/discovery/v1/type-format)` format)`  
Optional. Maximum number of the elements for Type.ARRAY.
`minItems``string (`[int64](https://developers.google.com/discovery/v1/type-format)` format)`  
Optional. Minimum number of the elements for Type.ARRAY.
`properties``map (key: string, value: object (`[Schema](https://ai.google.dev/api/caching#Schema)`))`  
Optional. Properties of Type.OBJECT.

An object containing a list of`"key": value`pairs. Example:`{ "name": "wrench", "mass": "1.3kg", "count": "3" }`.
`required[]``string`  
Optional. Required properties of Type.OBJECT.
`minProperties``string (`[int64](https://developers.google.com/discovery/v1/type-format)` format)`  
Optional. Minimum number of the properties for Type.OBJECT.
`maxProperties``string (`[int64](https://developers.google.com/discovery/v1/type-format)` format)`  
Optional. Maximum number of the properties for Type.OBJECT.
`minLength``string (`[int64](https://developers.google.com/discovery/v1/type-format)` format)`  
Optional. SCHEMA FIELDS FOR TYPE STRING Minimum length of the Type.STRING
`maxLength``string (`[int64](https://developers.google.com/discovery/v1/type-format)` format)`  
Optional. Maximum length of the Type.STRING
`pattern``string`  
Optional. Pattern of the Type.STRING to restrict a string to a regular expression.
`example``value (`[Value](https://protobuf.dev/reference/protobuf/google.protobuf/#value)` format)`  
Optional. Example of the object. Will only populated when the object is the root.
`anyOf[]``object (`[Schema](https://ai.google.dev/api/caching#Schema)`)`  
Optional. The value should be validated against any (one or more) of the subschemas in the list.
`propertyOrdering[]``string`  
Optional. The order of the properties. Not a standard field in open api spec. Used to determine the order of the properties in the response.
`default``value (`[Value](https://protobuf.dev/reference/protobuf/google.protobuf/#value)` format)`  
Optional. Default value of the field. Per JSON Schema, this field is intended for documentation generators and doesn't affect validation. Thus it's included here and ignored so that developers who send schemas with a`default`field don't get unknown-field errors.
`items``object (`[Schema](https://ai.google.dev/api/caching#Schema)`)`  
Optional. Schema of the elements of Type.ARRAY.
`minimum``number`  
Optional. SCHEMA FIELDS FOR TYPE INTEGER and NUMBER Minimum value of the Type.INTEGER and Type.NUMBER
`maximum``number`  
Optional. Maximum value of the Type.INTEGER and Type.NUMBER  

|                                                                                                                                                                                                                                                                                                                                   JSON representation                                                                                                                                                                                                                                                                                                                                   |
|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ``` { "type": enum (https://ai.google.dev/api/caching#Type), "format": string, "title": string, "description": string, "nullable": boolean, "enum": [ string ], "maxItems": string, "minItems": string, "properties": { string: { object (https://ai.google.dev/api/caching#Schema) }, ... }, "required": [ string ], "minProperties": string, "maxProperties": string, "minLength": string, "maxLength": string, "pattern": string, "example": value, "anyOf": [ { object (https://ai.google.dev/api/caching#Schema) } ], "propertyOrdering": [ string ], "default": value, "items": { object (https://ai.google.dev/api/caching#Schema) }, "minimum": number, "maximum": number } ``` |

## Type

Type contains the list of OpenAPI data types as defined by<https://spec.openapis.org/oas/v3.0.3#data-types>

|                         Enums                          ||
|--------------------|------------------------------------|
| `TYPE_UNSPECIFIED` | Not specified, should not be used. |
| `STRING`           | String type.                       |
| `NUMBER`           | Number type.                       |
| `INTEGER`          | Integer type.                      |
| `BOOLEAN`          | Boolean type.                      |
| `ARRAY`            | Array type.                        |
| `OBJECT`           | Object type.                       |
| `NULL`             | Null type.                         |

## Behavior

Defines the function behavior. Defaults to`BLOCKING`.

|                                                                                                                Enums                                                                                                                 ||
|----------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `UNSPECIFIED`  | This value is unused.                                                                                                                                                                                                |
| `BLOCKING`     | If set, the system will wait to receive the function response before continuing the conversation.                                                                                                                    |
| `NON_BLOCKING` | If set, the system will not wait to receive the function response. Instead, it will attempt to handle function responses as they become available while maintaining the conversation between the user and the model. |

## GoogleSearchRetrieval

Tool to retrieve public web data for grounding, powered by Google.
Fields`dynamicRetrievalConfig``object (`[DynamicRetrievalConfig](https://ai.google.dev/api/caching#DynamicRetrievalConfig)`)`  
Specifies the dynamic retrieval configuration for the given source.  

|                                             JSON representation                                             |
|-------------------------------------------------------------------------------------------------------------|
| ``` { "dynamicRetrievalConfig": { object (https://ai.google.dev/api/caching#DynamicRetrievalConfig) } } ``` |

## DynamicRetrievalConfig

Describes the options to customize dynamic retrieval.
Fields`mode``enum (`[Mode](https://ai.google.dev/api/caching#Mode)`)`  
The mode of the predictor to be used in dynamic retrieval.
`dynamicThreshold``number`  
The threshold to be used in dynamic retrieval. If not set, a system default value is used.  

|                                      JSON representation                                      |
|-----------------------------------------------------------------------------------------------|
| ``` { "mode": enum (https://ai.google.dev/api/caching#Mode), "dynamicThreshold": number } ``` |

## Mode

The mode of the predictor to be used in dynamic retrieval.

|                                    Enums                                    ||
|--------------------|---------------------------------------------------------|
| `MODE_UNSPECIFIED` | Always trigger retrieval.                               |
| `MODE_DYNAMIC`     | Run retrieval only when system decides it is necessary. |

## CodeExecution

This type has no fields.  
Tool that executes code generated by the model, and automatically returns the result to the model.

See also`ExecutableCode`and`CodeExecutionResult`which are only generated when using this tool.

## GoogleSearch

GoogleSearch tool type. Tool to support Google Search in Model. Powered by Google.
Fields`timeRangeFilter``object (`[Interval](https://ai.google.dev/api/caching#Interval)`)`  
Optional. Filter search results to a specific time range. If customers set a start time, they must set an end time (and vice versa).  

|                                  JSON representation                                   |
|----------------------------------------------------------------------------------------|
| ``` { "timeRangeFilter": { object (https://ai.google.dev/api/caching#Interval) } } ``` |

## Interval

Represents a time interval, encoded as a Timestamp start (inclusive) and a Timestamp end (exclusive).

The start must be less than or equal to the end. When the start equals the end, the interval is empty (matches no time). When both start and end are unspecified, the interval matches any time.
Fields`startTime``string (`[Timestamp](https://protobuf.dev/reference/protobuf/google.protobuf/#timestamp)` format)`  
Optional. Inclusive start of the interval.

If specified, a Timestamp matching this interval will have to be the same or after the start.

Uses RFC 3339, where generated output will always be Z-normalized and use 0, 3, 6 or 9 fractional digits. Offsets other than "Z" are also accepted. Examples:`"2014-10-02T15:01:23Z"`,`"2014-10-02T15:01:23.045123456Z"`or`"2014-10-02T15:01:23+05:30"`.
`endTime``string (`[Timestamp](https://protobuf.dev/reference/protobuf/google.protobuf/#timestamp)` format)`  
Optional. Exclusive end of the interval.

If specified, a Timestamp matching this interval will have to be before the end.

Uses RFC 3339, where generated output will always be Z-normalized and use 0, 3, 6 or 9 fractional digits. Offsets other than "Z" are also accepted. Examples:`"2014-10-02T15:01:23Z"`,`"2014-10-02T15:01:23.045123456Z"`or`"2014-10-02T15:01:23+05:30"`.  

|                JSON representation                 |
|----------------------------------------------------|
| ``` { "startTime": string, "endTime": string } ``` |

## ComputerUse

Computer Use tool type.
Fields`environment``enum (`[Environment](https://ai.google.dev/api/caching#Environment)`)`  
Required. The environment being operated.
`excludedPredefinedFunctions[]``string`  
Optional. By default, predefined functions are included in the final model call. Some of them can be explicitly excluded from being automatically included. This can serve two purposes: 1. Using a more restricted / different action space. 2. Improving the definitions / instructions of predefined functions.  

|                                                    JSON representation                                                     |
|----------------------------------------------------------------------------------------------------------------------------|
| ``` { "environment": enum (https://ai.google.dev/api/caching#Environment), "excludedPredefinedFunctions": [ string ] } ``` |

## Environment

Represents the environment being operated, such as a web browser.

|                         Enums                         ||
|---------------------------|----------------------------|
| `ENVIRONMENT_UNSPECIFIED` | Defaults to browser.       |
| `ENVIRONMENT_BROWSER`     | Operates in a web browser. |

## UrlContext

This type has no fields.  
Tool to support URL context retrieval.

## FileSearch

The FileSearch tool that retrieves knowledge from Semantic Retrieval corpora. Files are imported to Semantic Retrieval corpora using the ImportFile API.
Fields`fileSearchStoreNames[]``string`  
Required. The names of the fileSearchStores to retrieve from. Example:`fileSearchStores/my-file-search-store-123`
`metadataFilter``string`  
Optional. Metadata filter to apply to the semantic retrieval documents and chunks.
`topK``integer`  
Optional. The number of semantic retrieval chunks to retrieve.  

|                                    JSON representation                                    |
|-------------------------------------------------------------------------------------------|
| ``` { "fileSearchStoreNames": [ string ], "metadataFilter": string, "topK": integer } ``` |

## GoogleMaps

The GoogleMaps Tool that provides geospatial context for the user's query.
Fields`enableWidget``boolean`  
Optional. Whether to return a widget context token in the GroundingMetadata of the response. Developers can use the widget context token to render a Google Maps widget with geospatial context related to the places that the model references in the response.  

|         JSON representation         |
|-------------------------------------|
| ``` { "enableWidget": boolean } ``` |

## ToolConfig

The Tool configuration containing parameters for specifying`Tool`use in the request.
Fields`functionCallingConfig``object (`[FunctionCallingConfig](https://ai.google.dev/api/caching#FunctionCallingConfig)`)`  
Optional. Function calling config.
`retrievalConfig``object (`[RetrievalConfig](https://ai.google.dev/api/caching#RetrievalConfig)`)`  
Optional. Retrieval config.  

|                                                                                     JSON representation                                                                                      |
|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ``` { "functionCallingConfig": { object (https://ai.google.dev/api/caching#FunctionCallingConfig) }, "retrievalConfig": { object (https://ai.google.dev/api/caching#RetrievalConfig) } } ``` |

## FunctionCallingConfig

Configuration for specifying function calling behavior.
Fields`mode``enum (`[Mode](https://ai.google.dev/api/caching#Mode_1)`)`  
Optional. Specifies the mode in which function calling should execute. If unspecified, the default value will be set to AUTO.
`allowedFunctionNames[]``string`  
Optional. A set of function names that, when provided, limits the functions the model will call.

This should only be set when the Mode is ANY or VALIDATED. Function names should match \[FunctionDeclaration.name\]. When set, model will predict a function call from only allowed function names.  

|                                           JSON representation                                           |
|---------------------------------------------------------------------------------------------------------|
| ``` { "mode": enum (https://ai.google.dev/api/caching#Mode_1), "allowedFunctionNames": [ string ] } ``` |

## Mode

Defines the execution behavior for function calling by defining the execution mode.

|                                                                                                                                                                                     Enums                                                                                                                                                                                     ||
|--------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `MODE_UNSPECIFIED` | Unspecified function calling mode. This value should not be used.                                                                                                                                                                                                                                                                                         |
| `AUTO`             | Default model behavior, model decides to predict either a function call or a natural language response.                                                                                                                                                                                                                                                   |
| `ANY`              | Model is constrained to always predicting a function call only. If "allowedFunctionNames" are set, the predicted function call will be limited to any one of "allowedFunctionNames", else the predicted function call will be any one of the provided "functionDeclarations".                                                                             |
| `NONE`             | Model will not predict any function call. Model behavior is same as when not passing any function declarations.                                                                                                                                                                                                                                           |
| `VALIDATED`        | Model decides to predict either a function call or a natural language response, but will validate function calls with constrained decoding. If "allowedFunctionNames" are set, the predicted function call will be limited to any one of "allowedFunctionNames", else the predicted function call will be any one of the provided "functionDeclarations". |

## RetrievalConfig

Retrieval config.
Fields`latLng``object (`[LatLng](https://ai.google.dev/api/caching#LatLng)`)`  
Optional. The location of the user.
`languageCode``string`  
Optional. The language code of the user. Language code for content. Use language tags defined by[BCP47](https://www.rfc-editor.org/rfc/bcp/bcp47.txt).  

|                                         JSON representation                                         |
|-----------------------------------------------------------------------------------------------------|
| ``` { "latLng": { object (https://ai.google.dev/api/caching#LatLng) }, "languageCode": string } ``` |

## LatLng

An object that represents a latitude/longitude pair. This is expressed as a pair of doubles to represent degrees latitude and degrees longitude. Unless specified otherwise, this object must conform to the[WGS84 standard](https://en.wikipedia.org/wiki/World_Geodetic_System#1984_version). Values must be within normalized ranges.
Fields`latitude``number`  
The latitude in degrees. It must be in the range \[-90.0, +90.0\].
`longitude``number`  
The longitude in degrees. It must be in the range \[-180.0, +180.0\].  

|                 JSON representation                 |
|-----------------------------------------------------|
| ``` { "latitude": number, "longitude": number } ``` |

## UsageMetadata

Metadata on the usage of the cached content.
Fields`totalTokenCount``integer`  
Total number of tokens that the cached content consumes.  

|          JSON representation           |
|----------------------------------------|
| ``` { "totalTokenCount": integer } ``` |
