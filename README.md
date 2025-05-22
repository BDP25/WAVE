## **WAVE** - Wikipedia Analysis and Verification Engine

Simeon Flühmann (fluehsi2)  \
Elias Hager (hagereli) \
Joanna Gutbrod (gutbrjoa)


More Inforamtion about this Project can be found in the [Blogpost](https://bdp25.github.io/) here.



For deployment:

```sh
git clone this repo
```

move in to the src directory

```sh
cd src
```
build the needed docker image

```sh
docker compose --profle build build
```
run the compose (with -d if detached mode is needed)
```sh
docker compose --profile deploy up -d
```
