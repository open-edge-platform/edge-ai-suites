# Unit test guidelines
IMPORTANT: the unit tests are based on the demo DAVIS dataset. Make sure the application is successfully deployed and the demo dataset is properly prepared referring to the [get started guide](../docs/user-guide/get-started.md). You may use the script `prepare_demo_dataset.sh` for this purpose.

## A list of text queries and expected search results based on demo DAVIS dataset

| Query                  | Expected Result   |
|------------------------|-------------------|
| car                   | car-race          |
| deer                  | deer              |
| violin                | guitar-violin     |
| workout               | gym               |
| helicopter            | helicopter        |
| carousel in a park    | carousel          |
| monkeys               | monkeys-trees     |
| a cart on meadow      | golf              |
| rollercoaster         | rollercoaster     |
| horse riding          | horsejump-stick   |
| airplane              | planes-crossing   |
| tractor               | tractor           |

## Test manually
Start the web application as the [get started guide](../docs/user-guide/get-started.md) describes. Input the prompts from the list above one by one and check the returned result. You may check the result both visually and according to the list and the output log.

## Test with pytest tool
Please note that pytest does not guarantee visual correctness of the search results (i.e. how the result images and videos look like on the web page). It only covers part of the functionalities. To ensure a full coverage of the use cases of this application, please do tests manually.

```
bash run_app_ut.sh
```

## Warning
The vector DB will be cleared during the unit tests. DO NOT run the unit tests in the production environment.