The models endpoint provides a way for you to programmatically list the available models, and retrieve extended metadata such as supported functionality and context window sizing. Read more in[the Models guide](https://ai.google.dev/gemini-api/docs/models/gemini).  

## Method: models.get

- [Endpoint](https://ai.google.dev/api/models#body.HTTP_TEMPLATE)
- [Path parameters](https://ai.google.dev/api/models#body.PATH_PARAMETERS)
- [Request body](https://ai.google.dev/api/models#body.request_body)
- [Response body](https://ai.google.dev/api/models#body.response_body)
- [Authorization scopes](https://ai.google.dev/api/models#body.aspect)
- [Example request](https://ai.google.dev/api/models#body.codeSnippets)
  - [Get](https://ai.google.dev/api/models#body.codeSnippets.group)

Gets information about a specific`Model`such as its version number, token limits,[parameters](https://ai.google.dev/gemini-api/docs/models/generative-models#model-parameters)and other metadata. Refer to the[Gemini models guide](https://ai.google.dev/gemini-api/docs/models/gemini)for detailed model information.  

### Endpoint

get`https:``/``/generativelanguage.googleapis.com``/v1beta``/{name=models``/*}`  

### Path parameters

`name``string`  
Required. The resource name of the model.

This name should match a model name returned by the`models.list`method.

Format:`models/{model}`It takes the form`models/{model}`.

### Request body

The request body must be empty.  

### Example request

### Python

    from google import genai

    client = genai.Client()
    model_info = client.models.get(model="gemini-2.0-flash")
    print(model_info)  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/python/models.py#L41-L45

### Go

    ctx := context.Background()
    client, err := genai.NewClient(ctx, &genai.ClientConfig{
    	APIKey:  os.Getenv("GEMINI_API_KEY"),
    	Backend: genai.BackendGeminiAPI,
    })
    if err != nil {
    	log.Fatal(err)
    }

    modelInfo, err := client.Models.Get(ctx, "gemini-2.0-flash", nil)
    if err != nil {
    	log.Fatal(err)
    }

    fmt.Println(modelInfo)  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/go/models.go#L55-L69

### Shell

    curl https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash?key=$GEMINI_API_KEY  
    https://github.com/google-gemini/deprecated-generative-ai-python/blob/7a7cc5474ddaa0255a4410e05361028a24400abd/samples/rest/models.sh#L9-L10

### Response body

If successful, the response body contains an instance of[Model](https://ai.google.dev/api/models#Model).  

## Method: models.list

- [Endpoint](https://ai.google.dev/api/models#body.HTTP_TEMPLATE)
- [Query parameters](https://ai.google.dev/api/models#body.QUERY_PARAMETERS)
- [Request body](https://ai.google.dev/api/models#body.request_body)
- [Response body](https://ai.google.dev/api/models#body.response_body)
  - [JSON representation](https://ai.google.dev/api/models#body.ListModelsResponse.SCHEMA_REPRESENTATION)
- [Authorization scopes](https://ai.google.dev/api/models#body.aspect)
- [Example request](https://ai.google.dev/api/models#body.codeSnippets)
  - [List](https://ai.google.dev/api/models#body.codeSnippets.group)

Lists the[`Model`s](https://ai.google.dev/gemini-api/docs/models/gemini)available through the Gemini API.  

### Endpoint

get`https:``/``/generativelanguage.googleapis.com``/v1beta``/models`  

### Query parameters

`pageSize``integer`  
The maximum number of`Models`to return (per page).

If unspecified, 50 models will be returned per page. This method returns at most 1000 models per page, even if you pass a larger pageSize.
`pageToken``string`  
A page token, received from a previous`models.list`call.

Provide the`pageToken`returned by one request as an argument to the next request to retrieve the next page.

When paginating, all other parameters provided to`models.list`must match the call that provided the page token.

### Request body

The request body must be empty.  

### Example request

### Python

    from google import genai

    client = genai.Client()

    print("List of models that support generateContent:\n")
    for m in client.models.list():
        for action in m.supported_actions:
            if action == "generateContent":
                print(m.name)

    print("List of models that support embedContent:\n")
    for m in client.models.list():
        for action in m.supported_actions:
            if action == "embedContent":
                print(m.name)  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/python/models.py#L22-L36

### Go

    ctx := context.Background()
    client, err := genai.NewClient(ctx, &genai.ClientConfig{
    	APIKey:  os.Getenv("GEMINI_API_KEY"),
    	Backend: genai.BackendGeminiAPI,
    })
    if err != nil {
    	log.Fatal(err)
    }


    // Retrieve the list of models.
    models, err := client.Models.List(ctx, &genai.ListModelsConfig{})
    if err != nil {
    	log.Fatal(err)
    }

    fmt.Println("List of models that support generateContent:")
    for _, m := range models.Items {
    	for _, action := range m.SupportedActions {
    		if action == "generateContent" {
    			fmt.Println(m.Name)
    			break
    		}
    	}
    }

    fmt.Println("\nList of models that support embedContent:")
    for _, m := range models.Items {
    	for _, action := range m.SupportedActions {
    		if action == "embedContent" {
    			fmt.Println(m.Name)
    			break
    		}
    	}
    }  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/go/models.go#L14-L48

### Shell

    curl https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY  
    https://github.com/google-gemini/deprecated-generative-ai-python/blob/7a7cc5474ddaa0255a4410e05361028a24400abd/samples/rest/models.sh#L4-L5

### Response body

Response from`ListModel`containing a paginated list of Models.

If successful, the response body contains data with the following structure:
Fields`models[]``object (`[Model](https://ai.google.dev/api/models#Model)`)`  
The returned Models.
`nextPageToken``string`  
A token, which can be sent as`pageToken`to retrieve the next page.

If this field is omitted, there are no more pages.  

|                                          JSON representation                                           |
|--------------------------------------------------------------------------------------------------------|
| ``` { "models": [ { object (https://ai.google.dev/api/models#Model) } ], "nextPageToken": string } ``` |

## REST Resource: models

- [Resource: Model](https://ai.google.dev/api/models#Model)
  - [JSON representation](https://ai.google.dev/api/models#Model.SCHEMA_REPRESENTATION)
- [Methods](https://ai.google.dev/api/models#METHODS_SUMMARY)

## Resource: Model

Information about a Generative Language Model.
Fields`name``string`  
Required. The resource name of the`Model`. Refer to[Model variants](https://ai.google.dev/gemini-api/docs/models/gemini#model-variations)for all allowed values.

Format:`models/{model}`with a`{model}`naming convention of:

- "{baseModelId}-{version}"

Examples:

- `models/gemini-1.5-flash-001`
`baseModelId``string`  
Required. The name of the base model, pass this to the generation request.

Examples:

- `gemini-1.5-flash`
`version``string`  
Required. The version number of the model.

This represents the major version (`1.0`or`1.5`)
`displayName``string`  
The human-readable name of the model. E.g. "Gemini 1.5 Flash".

The name can be up to 128 characters long and can consist of any UTF-8 characters.
`description``string`  
A short description of the model.
`inputTokenLimit``integer`  
Maximum number of input tokens allowed for this model.
`outputTokenLimit``integer`  
Maximum number of output tokens available for this model.
`supportedGenerationMethods[]``string`  
The model's supported generation methods.

The corresponding API method names are defined as Pascal case strings, such as`generateMessage`and`generateContent`.
`thinking``boolean`  
Whether the model supports thinking.
`temperature``number`  
Controls the randomness of the output.

Values can range over`[0.0,maxTemperature]`, inclusive. A higher value will produce responses that are more varied, while a value closer to`0.0`will typically result in less surprising responses from the model. This value specifies default to be used by the backend while making the call to the model.
`maxTemperature``number`  
The maximum temperature this model can use.
`topP``number`  
For[Nucleus sampling](https://ai.google.dev/gemini-api/docs/prompting-strategies#top-p).

Nucleus sampling considers the smallest set of tokens whose probability sum is at least`topP`. This value specifies default to be used by the backend while making the call to the model.
`topK``integer`  
For Top-k sampling.

Top-k sampling considers the set of`topK`most probable tokens. This value specifies default to be used by the backend while making the call to the model. If empty, indicates the model doesn't use top-k sampling, and`topK`isn't allowed as a generation parameter.  

|                                                                                                                                                     JSON representation                                                                                                                                                      |
|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ``` { "name": string, "baseModelId": string, "version": string, "displayName": string, "description": string, "inputTokenLimit": integer, "outputTokenLimit": integer, "supportedGenerationMethods": [ string ], "thinking": boolean, "temperature": number, "maxTemperature": number, "topP": number, "topK": integer } ``` |

## Method: models.predict

- [Endpoint](https://ai.google.dev/api/models#body.HTTP_TEMPLATE)
- [Path parameters](https://ai.google.dev/api/models#body.PATH_PARAMETERS)
- [Request body](https://ai.google.dev/api/models#body.request_body)
  - [JSON representation](https://ai.google.dev/api/models#body.request_body.SCHEMA_REPRESENTATION)
- [Response body](https://ai.google.dev/api/models#body.response_body)
  - [JSON representation](https://ai.google.dev/api/models#body.PredictResponse.SCHEMA_REPRESENTATION)
- [Authorization scopes](https://ai.google.dev/api/models#body.aspect)

Performs a prediction request.  

### Endpoint

post`https:``/``/generativelanguage.googleapis.com``/v1beta``/{model=models``/*}:predict`  

### Path parameters

`model``string`  
Required. The name of the model for prediction. Format:`name=models/{model}`. It takes the form`models/{model}`.

### Request body

The request body contains data with the following structure:
Fields`instances[]``value (`[Value](https://protobuf.dev/reference/protobuf/google.protobuf/#value)` format)`  
Required. The instances that are the input to the prediction call.
`parameters``value (`[Value](https://protobuf.dev/reference/protobuf/google.protobuf/#value)` format)`  
Optional. The parameters that govern the prediction call.  

### Response body

Response message for \[PredictionService.Predict\].

If successful, the response body contains data with the following structure:
Fields`predictions[]``value (`[Value](https://protobuf.dev/reference/protobuf/google.protobuf/#value)` format)`  
The outputs of the prediction call.  

|         JSON representation          |
|--------------------------------------|
| ``` { "predictions": [ value ] } ``` |

## Method: models.predictLongRunning

- [Endpoint](https://ai.google.dev/api/models#body.HTTP_TEMPLATE)
- [Path parameters](https://ai.google.dev/api/models#body.PATH_PARAMETERS)
- [Request body](https://ai.google.dev/api/models#body.request_body)
  - [JSON representation](https://ai.google.dev/api/models#body.request_body.SCHEMA_REPRESENTATION)
- [Response body](https://ai.google.dev/api/models#body.response_body)
- [Authorization scopes](https://ai.google.dev/api/models#body.aspect)

Same as models.predict but returns an LRO.  

### Endpoint

post`https:``/``/generativelanguage.googleapis.com``/v1beta``/{model=models``/*}:predictLongRunning`  

### Path parameters

`model``string`  
Required. The name of the model for prediction. Format:`name=models/{model}`.

### Request body

The request body contains data with the following structure:
Fields`instances[]``value (`[Value](https://protobuf.dev/reference/protobuf/google.protobuf/#value)` format)`  
Required. The instances that are the input to the prediction call.
`parameters``value (`[Value](https://protobuf.dev/reference/protobuf/google.protobuf/#value)` format)`  
Optional. The parameters that govern the prediction call.  

### Response body

If successful, the response body contains an instance of[Operation](https://ai.google.dev/api/batch-api#Operation).
