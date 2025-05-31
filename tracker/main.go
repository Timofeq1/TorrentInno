package main

import (
	"fmt"
	"github.com/gin-gonic/gin"
	"net/http"
	"sync"
	"time"
)

type Peer struct {
	PeerId     string `json:"peerId"`
	InfoHash   string `json:"infoHash"`
	PublicIp   string `json:"publicIp"`
	PublicPort string `json:"publicPort"`
	UpdatedAt  int64  `json:"-"`
}

const PeerLifespan = 35

type Peers struct {
	mu sync.Mutex
	v  map[string]map[string]Peer
}

var peers = Peers{v: make(map[string]map[string]Peer)}

func main() {

	//start peers cleaning task
	go tick(1)

	router := gin.New()
	router.Use(
		gin.Recovery(),
	)
	router.GET("/peers", getPeers)
	router.POST("/peers", updatePeer)
	s := &http.Server{
		Addr:           ":8080",
		Handler:        router,
		ReadTimeout:    10 * time.Second,
		WriteTimeout:   10 * time.Second,
		MaxHeaderBytes: 1 << 20,
	}
	err := s.ListenAndServe()

	if err != nil {
		fmt.Print(err)
		return
	}

}

func updatePeer(context *gin.Context) {
	peers.mu.Lock()
	defer peers.mu.Unlock()
	var updatedPeer Peer
	if err := context.BindJSON(&updatedPeer); err != nil {
		fmt.Println(err)
		err = context.AbortWithError(http.StatusBadRequest, err)
		return
	}

	updatedPeer.UpdatedAt = time.Now().Unix()
	if _, ok := peers.v[updatedPeer.InfoHash]; !ok {
		peers.v[updatedPeer.InfoHash] = make(map[string]Peer)
	}
	peers.v[updatedPeer.InfoHash][updatedPeer.PeerId] = updatedPeer

	type Response struct {
		InfoHash string `json:"infoHash"`
		Peers    []Peer `json:"peers"`
	}

	var response Response
	response.InfoHash = updatedPeer.InfoHash
	for _, peer := range peers.v[updatedPeer.InfoHash] {
		response.Peers = append(response.Peers, peer)
	}

	context.JSON(http.StatusOK, response)
}

func getPeers(context *gin.Context) {
	peers.mu.Lock()
	defer peers.mu.Unlock()
	context.JSON(http.StatusOK, peers.v)
}

func tick(n time.Duration) {
	for range time.Tick(n * time.Second) {
		peers.mu.Lock()
		currentTime := time.Now().Unix()
		for hash, friends := range peers.v {
			for peerId, peer := range friends {
				if peer.UpdatedAt+PeerLifespan < currentTime {
					fmt.Printf("Peer %s seems to death. Removing..", peerId)
					delete(peers.v[hash], peerId)
				}
			}
		}
		peers.mu.Unlock()
	}
}
