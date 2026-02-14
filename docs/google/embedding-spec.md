Embeddings are a numerical representation of text input that open up a number of unique use cases, such as clustering, similarity measurement and information retrieval. For an introduction, check out the[Embeddings guide](https://ai.google.dev/gemini-api/docs/embeddings).

Unlike generative AI models that create new content, the Gemini Embedding model is only intended to transform the format of your input data into a numerical representation. While Google is responsible for providing an embedding model that transforms the format of your input data to the numerical-format requested, users retain full responsibility for the data they input and the resulting embeddings. By using the Gemini Embedding model you confirm that you have the necessary rights to any content that you upload. Do not generate content that infringes on others' intellectual property or privacy rights. Your use of this service is subject to our[Prohibited Use Policy](https://policies.google.com/terms/generative-ai/use-policy)and[Google's Terms of Service](https://ai.google.dev/gemini-api/terms).  

## Method: models.embedContent

- [Endpoint](https://ai.google.dev/api/embeddings#body.HTTP_TEMPLATE)
- [Path parameters](https://ai.google.dev/api/embeddings#body.PATH_PARAMETERS)
- [Request body](https://ai.google.dev/api/embeddings#body.request_body)
  - [JSON representation](https://ai.google.dev/api/embeddings#body.request_body.SCHEMA_REPRESENTATION)
- [Response body](https://ai.google.dev/api/embeddings#body.response_body)
- [Authorization scopes](https://ai.google.dev/api/embeddings#body.aspect)
- [Example request](https://ai.google.dev/api/embeddings#body.codeSnippets)
  - [Basic](https://ai.google.dev/api/embeddings#body.codeSnippets.group)

Generates a text embedding vector from the input`Content`using the specified[Gemini Embedding model](https://ai.google.dev/gemini-api/docs/models/gemini#text-embedding).  

### Endpoint

post`https:``/``/generativelanguage.googleapis.com``/v1beta``/{model=models``/*}:embedContent`  

### Path parameters

`model``string`  
Required. The model's resource name. This serves as an ID for the Model to use.

This name should match a model name returned by the`models.list`method.

Format:`models/{model}`It takes the form`models/{model}`.

### Request body

The request body contains data with the following structure:
Fields`content``object (`[Content](https://ai.google.dev/api/caching#Content)`)`  
Required. The content to embed. Only the`parts.text`fields will be counted.
`taskType``enum (`[TaskType](https://ai.google.dev/api/embeddings#v1beta.TaskType)`)`  
Optional. Optional task type for which the embeddings will be used. Not supported on earlier models (`models/embedding-001`).
`title``string`  
Optional. An optional title for the text. Only applicable when TaskType is`RETRIEVAL_DOCUMENT`.

Note: Specifying a`title`for`RETRIEVAL_DOCUMENT`provides better quality embeddings for retrieval.
`outputDimensionality``integer`  
Optional. Optional reduced dimension for the output embedding. If set, excessive values in the output embedding are truncated from the end. Supported by newer models since 2024 only. You cannot set this value if using the earlier model (`models/embedding-001`).  

### Example request

### Python

    from google import genai
    from google.genai import types

    client = genai.Client()
    text = "Hello World!"
    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=10),
    )
    print(result.embeddings)  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/python/embed.py#L22-L32

### Node.js

    // Make sure to include the following import:
    // import {GoogleGenAI} from '@google/genai';
    const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
    const text = "Hello World!";
    const result = await ai.models.embedContent({
      model: "gemini-embedding-001",
      contents: text,
      config: { outputDimensionality: 10 },
    });
    console.log(result.embeddings);  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/javascript/embed.js#L22-L31

### Go

    ctx := context.Background()
    client, err := genai.NewClient(ctx, &genai.ClientConfig{
    	APIKey:  os.Getenv("GEMINI_API_KEY"),
    	Backend: genai.BackendGeminiAPI,
    })
    if err != nil {
    	log.Fatal(err)
    }

    text := "Hello World!"
    outputDim := int32(10)
    contents := []*genai.Content{
    	genai.NewContentFromText(text, genai.RoleUser),
    }
    result, err := client.Models.EmbedContent(ctx, "gemini-embedding-001", 
    	contents, &genai.EmbedContentConfig{
    		OutputDimensionality: &outputDim,
    })
    if err != nil {
    	log.Fatal(err)
    }

    embeddings, err := json.MarshalIndent(result.Embeddings, "", "  ")
    if err != nil {
    	log.Fatal(err)
    }
    fmt.Println(string(embeddings))  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/go/embed.go#L15-L41

### Shell

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent" \
    -H "x-goog-api-key: $GEMINI_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{"model": "models/gemini-embedding-001",
         "content": {
         "parts":[{
         "text": "What is the meaning of life?"}]}
        }'  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/rest/embed.sh#L4-L12

### Response body

If successful, the response body contains an instance of[EmbedContentResponse](https://ai.google.dev/api/embeddings#v1beta.EmbedContentResponse).  

## Method: models.batchEmbedContents

- [Endpoint](https://ai.google.dev/api/embeddings#body.HTTP_TEMPLATE)
- [Path parameters](https://ai.google.dev/api/embeddings#body.PATH_PARAMETERS)
- [Request body](https://ai.google.dev/api/embeddings#body.request_body)
  - [JSON representation](https://ai.google.dev/api/embeddings#body.request_body.SCHEMA_REPRESENTATION)
- [Response body](https://ai.google.dev/api/embeddings#body.response_body)
  - [JSON representation](https://ai.google.dev/api/embeddings#body.BatchEmbedContentsResponse.SCHEMA_REPRESENTATION)
- [Authorization scopes](https://ai.google.dev/api/embeddings#body.aspect)
- [Example request](https://ai.google.dev/api/embeddings#body.codeSnippets)
  - [Basic](https://ai.google.dev/api/embeddings#body.codeSnippets.group)

Generates multiple embedding vectors from the input`Content`which consists of a batch of strings represented as`EmbedContentRequest`objects.  

### Endpoint

post`https:``/``/generativelanguage.googleapis.com``/v1beta``/{model=models``/*}:batchEmbedContents`  

### Path parameters

`model``string`  
Required. The model's resource name. This serves as an ID for the Model to use.

This name should match a model name returned by the`models.list`method.

Format:`models/{model}`It takes the form`models/{model}`.

### Request body

The request body contains data with the following structure:
Fields`requests[]``object (`[EmbedContentRequest](https://ai.google.dev/api/batch-api#EmbedContentRequest)`)`  
Required. Embed requests for the batch. The model in each of these requests must match the model specified`BatchEmbedContentsRequest.model`.  

### Example request

### Python

    from google import genai
    from google.genai import types

    client = genai.Client()
    texts = [
        "What is the meaning of life?",
        "How much wood would a woodchuck chuck?",
        "How does the brain work?",
    ]
    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents=texts,
        config=types.EmbedContentConfig(output_dimensionality=10),
    )
    print(result.embeddings)  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/python/embed.py#L37-L51

### Node.js

    // Make sure to include the following import:
    // import {GoogleGenAI} from '@google/genai';
    const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
    const texts = [
      "What is the meaning of life?",
      "How much wood would a woodchuck chuck?",
      "How does the brain work?",
    ];
    const result = await ai.models.embedContent({
      model: "gemini-embedding-001",
      contents: texts,
      config: { outputDimensionality: 10 },
    });
    console.log(result.embeddings);  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/javascript/embed.js#L38-L51

### Go

    ctx := context.Background()
    client, err := genai.NewClient(ctx, &genai.ClientConfig{
    	APIKey:  os.Getenv("GEMINI_API_KEY"),
    	Backend: genai.BackendGeminiAPI,
    })
    if err != nil {
    	log.Fatal(err)
    }

    contents := []*genai.Content{
    	genai.NewContentFromText("What is the meaning of life?", genai.RoleUser),
    	genai.NewContentFromText("How much wood would a woodchuck chuck?", genai.RoleUser),
    	genai.NewContentFromText("How does the brain work?", genai.RoleUser),
    }

    outputDim := int32(10)
    result, err := client.Models.EmbedContent(ctx, "gemini-embedding-001", contents, &genai.EmbedContentConfig{
    	OutputDimensionality: &outputDim,
    })
    if err != nil {
    	log.Fatal(err)
    }

    embeddings, err := json.MarshalIndent(result.Embeddings, "", "  ")
    if err != nil {
    	log.Fatal(err)
    }
    fmt.Println(string(embeddings))  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/go/embed.go#L48-L75

### Shell

    curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents" \
    -H "x-goog-api-key: $GEMINI_API_KEY" \
    -H 'Content-Type: application/json' \
    -d '{"requests": [{
          "model": "models/gemini-embedding-001",
          "content": {
          "parts":[{
            "text": "What is the meaning of life?"}]}, },
          {
          "model": "models/gemini-embedding-001",
          "content": {
          "parts":[{
            "text": "How much wood would a woodchuck chuck?"}]}, },
          {
          "model": "models/gemini-embedding-001",
          "content": {
          "parts":[{
            "text": "How does the brain work?"}]}, }, ]}' 2> /dev/null | grep -C 5 values  
    https://github.com/google-gemini/api-examples/blob/856e8a0f566a2810625cecabba6e2ab1fe97e496/rest/embed.sh#L16-L34

### Response body

The response to a`BatchEmbedContentsRequest`.

If successful, the response body contains data with the following structure:
Fields`embeddings[]``object (`[ContentEmbedding](https://ai.google.dev/api/embeddings#v1beta.ContentEmbedding)`)`  
Output only. The embeddings for each request, in the same order as provided in the batch request.  

|                                           JSON representation                                           |
|---------------------------------------------------------------------------------------------------------|
| ``` { "embeddings": [ { object (https://ai.google.dev/api/embeddings#v1beta.ContentEmbedding) } ] } ``` |

## Method: models.asyncBatchEmbedContent

- [Endpoint](https://ai.google.dev/api/embeddings#body.HTTP_TEMPLATE)
- [Path parameters](https://ai.google.dev/api/embeddings#body.PATH_PARAMETERS)
- [Request body](https://ai.google.dev/api/embeddings#body.request_body)
  - [JSON representation](https://ai.google.dev/api/embeddings#body.request_body.SCHEMA_REPRESENTATION)
    - [JSON representation](https://ai.google.dev/api/embeddings#body.request_body.SCHEMA_REPRESENTATION.batch.SCHEMA_REPRESENTATION)
    - [JSON representation](https://ai.google.dev/api/embeddings#body.request_body.SCHEMA_REPRESENTATION.batch.SCHEMA_REPRESENTATION_1)
    - [JSON representation](https://ai.google.dev/api/embeddings#body.request_body.SCHEMA_REPRESENTATION.batch.SCHEMA_REPRESENTATION_2)
- [Response body](https://ai.google.dev/api/embeddings#body.response_body)
- [Authorization scopes](https://ai.google.dev/api/embeddings#body.aspect)

Enqueues a batch of`models.embedContent`requests for batch processing. We have a`models.batchEmbedContents`handler in`GenerativeService`, but it was synchronized. So we name this one to be`Async`to avoid confusion.  

### Endpoint

post`https:``/``/generativelanguage.googleapis.com``/v1beta``/{batch.model=models``/*}:asyncBatchEmbedContent`  

### Path parameters

`batch.model``string`  
Required. The name of the`Model`to use for generating the completion.

Format:`models/{model}`. It takes the form`models/{model}`.

### Request body

The request body contains data with the following structure:
Fields`batch.name``string`  
Output only. Identifier. Resource name of the batch.

Format:`batches/{batchId}`.
`batch.displayName``string`  
Required. The user-defined name of this batch.
`batch.inputConfig``object (`[InputEmbedContentConfig](https://ai.google.dev/api/embeddings#InputEmbedContentConfig)`)`  
Required. Input configuration of the instances on which batch processing are performed.
`batch.output``object (`[EmbedContentBatchOutput](https://ai.google.dev/api/embeddings#EmbedContentBatchOutput)`)`  
Output only. The output of the batch request.
`batch.createTime``string (`[Timestamp](https://protobuf.dev/reference/protobuf/google.protobuf/#timestamp)` format)`  
Output only. The time at which the batch was created.

Uses RFC 3339, where generated output will always be Z-normalized and use 0, 3, 6 or 9 fractional digits. Offsets other than "Z" are also accepted. Examples:`"2014-10-02T15:01:23Z"`,`"2014-10-02T15:01:23.045123456Z"`or`"2014-10-02T15:01:23+05:30"`.
`batch.endTime``string (`[Timestamp](https://protobuf.dev/reference/protobuf/google.protobuf/#timestamp)` format)`  
Output only. The time at which the batch processing completed.

Uses RFC 3339, where generated output will always be Z-normalized and use 0, 3, 6 or 9 fractional digits. Offsets other than "Z" are also accepted. Examples:`"2014-10-02T15:01:23Z"`,`"2014-10-02T15:01:23.045123456Z"`or`"2014-10-02T15:01:23+05:30"`.
`batch.updateTime``string (`[Timestamp](https://protobuf.dev/reference/protobuf/google.protobuf/#timestamp)` format)`  
Output only. The time at which the batch was last updated.

Uses RFC 3339, where generated output will always be Z-normalized and use 0, 3, 6 or 9 fractional digits. Offsets other than "Z" are also accepted. Examples:`"2014-10-02T15:01:23Z"`,`"2014-10-02T15:01:23.045123456Z"`or`"2014-10-02T15:01:23+05:30"`.
`batch.batchStats``object (`[EmbedContentBatchStats](https://ai.google.dev/api/embeddings#EmbedContentBatchStats)`)`  
Output only. Stats about the batch.
`batch.state``enum (`[BatchState](https://ai.google.dev/api/batch-api#v1beta.BatchState)`)`  
Output only. The state of the batch.
`batch.priority``string (`[int64](https://developers.google.com/discovery/v1/type-format)` format)`  
Optional. The priority of the batch. Batches with a higher priority value will be processed before batches with a lower priority value. Negative values are allowed. Default is 0.  

### Response body

If successful, the response body contains an instance of[Operation](https://ai.google.dev/api/batch-api#Operation).  

## EmbedContentResponse

- [JSON representation](https://ai.google.dev/api/embeddings#SCHEMA_REPRESENTATION)

The response to an`EmbedContentRequest`.
Fields`embedding``object (`[ContentEmbedding](https://ai.google.dev/api/embeddings#v1beta.ContentEmbedding)`)`  
Output only. The embedding generated from the input content.  

|                                        JSON representation                                         |
|----------------------------------------------------------------------------------------------------|
| ``` { "embedding": { object (https://ai.google.dev/api/embeddings#v1beta.ContentEmbedding) } } ``` |

## ContentEmbedding

- [JSON representation](https://ai.google.dev/api/embeddings#SCHEMA_REPRESENTATION)

A list of floats representing an embedding.
Fields`values[]``number`  
The embedding values.  

|       JSON representation        |
|----------------------------------|
| ``` { "values": [ number ] } ``` |

## TaskType

Type of task for which the embedding will be used.

|                                              Enums                                              ||
|-------------------------|------------------------------------------------------------------------|
| `TASK_TYPE_UNSPECIFIED` | Unset value, which will default to one of the other enum values.       |
| `RETRIEVAL_QUERY`       | Specifies the given text is a query in a search/retrieval setting.     |
| `RETRIEVAL_DOCUMENT`    | Specifies the given text is a document from the corpus being searched. |
| `SEMANTIC_SIMILARITY`   | Specifies the given text will be used for STS.                         |
| `CLASSIFICATION`        | Specifies that the given text will be classified.                      |
| `CLUSTERING`            | Specifies that the embeddings will be used for clustering.             |
| `QUESTION_ANSWERING`    | Specifies that the given text will be used for question answering.     |
| `FACT_VERIFICATION`     | Specifies that the given text will be used for fact verification.      |
| `CODE_RETRIEVAL_QUERY`  | Specifies that the given text will be used for code retrieval.         |

## EmbedContentBatch

- [JSON representation](https://ai.google.dev/api/embeddings#SCHEMA_REPRESENTATION)
- [InputEmbedContentConfig](https://ai.google.dev/api/embeddings#InputEmbedContentConfig)
  - [JSON representation](https://ai.google.dev/api/embeddings#InputEmbedContentConfig.SCHEMA_REPRESENTATION)
- [InlinedEmbedContentRequests](https://ai.google.dev/api/embeddings#InlinedEmbedContentRequests)
  - [JSON representation](https://ai.google.dev/api/embeddings#InlinedEmbedContentRequests.SCHEMA_REPRESENTATION)
- [InlinedEmbedContentRequest](https://ai.google.dev/api/embeddings#InlinedEmbedContentRequest)
  - [JSON representation](https://ai.google.dev/api/embeddings#InlinedEmbedContentRequest.SCHEMA_REPRESENTATION)
- [EmbedContentBatchOutput](https://ai.google.dev/api/embeddings#EmbedContentBatchOutput)
  - [JSON representation](https://ai.google.dev/api/embeddings#EmbedContentBatchOutput.SCHEMA_REPRESENTATION)
- [InlinedEmbedContentResponses](https://ai.google.dev/api/embeddings#InlinedEmbedContentResponses)
  - [JSON representation](https://ai.google.dev/api/embeddings#InlinedEmbedContentResponses.SCHEMA_REPRESENTATION)
- [InlinedEmbedContentResponse](https://ai.google.dev/api/embeddings#InlinedEmbedContentResponse)
  - [JSON representation](https://ai.google.dev/api/embeddings#InlinedEmbedContentResponse.SCHEMA_REPRESENTATION)
- [EmbedContentBatchStats](https://ai.google.dev/api/embeddings#EmbedContentBatchStats)
  - [JSON representation](https://ai.google.dev/api/embeddings#EmbedContentBatchStats.SCHEMA_REPRESENTATION)

A resource representing a batch of`EmbedContent`requests.
Fields`model``string`  
Required. The name of the`Model`to use for generating the completion.

Format:`models/{model}`.
`name``string`  
Output only. Identifier. Resource name of the batch.

Format:`batches/{batchId}`.
`displayName``string`  
Required. The user-defined name of this batch.
`inputConfig``object (`[InputEmbedContentConfig](https://ai.google.dev/api/embeddings#InputEmbedContentConfig)`)`  
Required. Input configuration of the instances on which batch processing are performed.
`output``object (`[EmbedContentBatchOutput](https://ai.google.dev/api/embeddings#EmbedContentBatchOutput)`)`  
Output only. The output of the batch request.
`createTime``string (`[Timestamp](https://protobuf.dev/reference/protobuf/google.protobuf/#timestamp)` format)`  
Output only. The time at which the batch was created.

Uses RFC 3339, where generated output will always be Z-normalized and use 0, 3, 6 or 9 fractional digits. Offsets other than "Z" are also accepted. Examples:`"2014-10-02T15:01:23Z"`,`"2014-10-02T15:01:23.045123456Z"`or`"2014-10-02T15:01:23+05:30"`.
`endTime``string (`[Timestamp](https://protobuf.dev/reference/protobuf/google.protobuf/#timestamp)` format)`  
Output only. The time at which the batch processing completed.

Uses RFC 3339, where generated output will always be Z-normalized and use 0, 3, 6 or 9 fractional digits. Offsets other than "Z" are also accepted. Examples:`"2014-10-02T15:01:23Z"`,`"2014-10-02T15:01:23.045123456Z"`or`"2014-10-02T15:01:23+05:30"`.
`updateTime``string (`[Timestamp](https://protobuf.dev/reference/protobuf/google.protobuf/#timestamp)` format)`  
Output only. The time at which the batch was last updated.

Uses RFC 3339, where generated output will always be Z-normalized and use 0, 3, 6 or 9 fractional digits. Offsets other than "Z" are also accepted. Examples:`"2014-10-02T15:01:23Z"`,`"2014-10-02T15:01:23.045123456Z"`or`"2014-10-02T15:01:23+05:30"`.
`batchStats``object (`[EmbedContentBatchStats](https://ai.google.dev/api/embeddings#EmbedContentBatchStats)`)`  
Output only. Stats about the batch.
`state``enum (`[BatchState](https://ai.google.dev/api/batch-api#v1beta.BatchState)`)`  
Output only. The state of the batch.
`priority``string (`[int64](https://developers.google.com/discovery/v1/type-format)` format)`  
Optional. The priority of the batch. Batches with a higher priority value will be processed before batches with a lower priority value. Negative values are allowed. Default is 0.  

|                                                                                                                                                                                                                                         JSON representation                                                                                                                                                                                                                                         |
|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ``` { "model": string, "name": string, "displayName": string, "inputConfig": { object (https://ai.google.dev/api/embeddings#InputEmbedContentConfig) }, "output": { object (https://ai.google.dev/api/embeddings#EmbedContentBatchOutput) }, "createTime": string, "endTime": string, "updateTime": string, "batchStats": { object (https://ai.google.dev/api/embeddings#EmbedContentBatchStats) }, "state": enum (https://ai.google.dev/api/batch-api#v1beta.BatchState), "priority": string } ``` |

## InputEmbedContentConfig

Configures the input to the batch request.
Fields  
`source``Union type`  
Required. The source of the input.`source`can be only one of the following:
`fileName``string`  
The name of the`File`containing the input requests.
`requests``object (`[InlinedEmbedContentRequests](https://ai.google.dev/api/embeddings#InlinedEmbedContentRequests)`)`  
The requests to be processed in the batch.  

|                                                                JSON representation                                                                |
|---------------------------------------------------------------------------------------------------------------------------------------------------|
| ``` { // source "fileName": string, "requests": { object (https://ai.google.dev/api/embeddings#InlinedEmbedContentRequests) } // Union type } ``` |

## InlinedEmbedContentRequests

The requests to be processed in the batch if provided as part of the batch creation request.
Fields`requests[]``object (`[InlinedEmbedContentRequest](https://ai.google.dev/api/embeddings#InlinedEmbedContentRequest)`)`  
Required. The requests to be processed in the batch.  

|                                           JSON representation                                            |
|----------------------------------------------------------------------------------------------------------|
| ``` { "requests": [ { object (https://ai.google.dev/api/embeddings#InlinedEmbedContentRequest) } ] } ``` |

## InlinedEmbedContentRequest

The request to be processed in the batch.
Fields`request``object (`[EmbedContentRequest](https://ai.google.dev/api/batch-api#EmbedContentRequest)`)`  
Required. The request to be processed in the batch.
`metadata``object (`[Struct](https://protobuf.dev/reference/protobuf/google.protobuf/#struct)` format)`  
Optional. The metadata to be associated with the request.  

|                                                 JSON representation                                                 |
|---------------------------------------------------------------------------------------------------------------------|
| ``` { "request": { object (https://ai.google.dev/api/batch-api#EmbedContentRequest) }, "metadata": { object } } ``` |

## EmbedContentBatchOutput

The output of a batch request. This is returned in the`AsyncBatchEmbedContentResponse`or the`EmbedContentBatch.output`field.
Fields  
`output``Union type`  
The output of the batch request.`output`can be only one of the following:
`responsesFile``string`  
Output only. The file ID of the file containing the responses. The file will be a JSONL file with a single response per line. The responses will be`EmbedContentResponse`messages formatted as JSON. The responses will be written in the same order as the input requests.
`inlinedResponses``object (`[InlinedEmbedContentResponses](https://ai.google.dev/api/embeddings#InlinedEmbedContentResponses)`)`  
Output only. The responses to the requests in the batch. Returned when the batch was built using inlined requests. The responses will be in the same order as the input requests.  

|                                                                       JSON representation                                                                       |
|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ``` { // output "responsesFile": string, "inlinedResponses": { object (https://ai.google.dev/api/embeddings#InlinedEmbedContentResponses) } // Union type } ``` |

## InlinedEmbedContentResponses

The responses to the requests in the batch.
Fields`inlinedResponses[]``object (`[InlinedEmbedContentResponse](https://ai.google.dev/api/embeddings#InlinedEmbedContentResponse)`)`  
Output only. The responses to the requests in the batch.  

|                                                JSON representation                                                |
|-------------------------------------------------------------------------------------------------------------------|
| ``` { "inlinedResponses": [ { object (https://ai.google.dev/api/embeddings#InlinedEmbedContentResponse) } ] } ``` |

## InlinedEmbedContentResponse

The response to a single request in the batch.
Fields`metadata``object (`[Struct](https://protobuf.dev/reference/protobuf/google.protobuf/#struct)` format)`  
Output only. The metadata associated with the request.  
`output``Union type`  
The output of the request.`output`can be only one of the following:
`error``object (`[Status](https://ai.google.dev/api/files#v1beta.Status)`)`  
Output only. The error encountered while processing the request.
`response``object (`[EmbedContentResponse](https://ai.google.dev/api/embeddings#v1beta.EmbedContentResponse)`)`  
Output only. The response to the request.  

|                                                                                                    JSON representation                                                                                                     |
|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ``` { "metadata": { object }, // output "error": { object (https://ai.google.dev/api/files#v1beta.Status) }, "response": { object (https://ai.google.dev/api/embeddings#v1beta.EmbedContentResponse) } // Union type } ``` |

## EmbedContentBatchStats

Stats about the batch.
Fields`requestCount``string (`[int64](https://developers.google.com/discovery/v1/type-format)` format)`  
Output only. The number of requests in the batch.
`successfulRequestCount``string (`[int64](https://developers.google.com/discovery/v1/type-format)` format)`  
Output only. The number of requests that were successfully processed.
`failedRequestCount``string (`[int64](https://developers.google.com/discovery/v1/type-format)` format)`  
Output only. The number of requests that failed to be processed.
`pendingRequestCount``string (`[int64](https://developers.google.com/discovery/v1/type-format)` format)`  
Output only. The number of requests that are still pending processing.  

|                                                        JSON representation                                                        |
|-----------------------------------------------------------------------------------------------------------------------------------|
| ``` { "requestCount": string, "successfulRequestCount": string, "failedRequestCount": string, "pendingRequestCount": string } ``` |
