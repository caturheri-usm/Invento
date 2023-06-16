
# INVENTO

Looking out in the real world, there are no applications or implementations (as far as we know) that allow users to collaborate on small to medium size projects. Those are only served for big size projects where the stakes are high and involve billions of rupiahs (ex. tender project). This cemented our idea to make an application specifically for this problem.



## Machine Learning Model
We will use the Neural Collaborative Filtering (NCF) model. The input for this model is the item vector consisting of the user ID and project ID, and the true label represents the interaction between the user and the item.
![Model Arsitektur](https://github.com/caturheri-usm/Invento/assets/114671113/9ffea33d-e601-41de-9cbe-5f3090140f6f)
## 
Features

- Recommendation based on user interacting with item
- Profile user
- Join user admin proyek

## REST API
We designed and built a REST API using FastAPI to execute commands according to the planned application flow. The API was deployed to Google Cloud Run, a serverless compute platform, ensuring scalability and availability. This enabled Mobile Developers (MD) to easily integrate and utilize the API for their applications, while benefiting from the scalability and managed infrastructure provided by Cloud Run.

The following is the documentation of the rest api that we have built:
[restapidocs]
##
