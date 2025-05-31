# Resource Manager API

## Constructor
```python
def __init__(
        self,
        host_peer_id: str,
        destination: Path,
        resource: Resource,
):
    """
    Create a new ResourceManager instance. 
    IMPORTANT: For pair (destination, resource) there MUST be only one instance of (running) `ResourceManager`. 
    Otherwise, the whole behaviour is undefined. 

    :param host_peer_id: the peer_id that will host the resource
    :param destination: The destination of the file on the filesystem. Important: if the destination exists
    on the moment the class is instantiated, then it's assumed that the caller has the `destination` file
    and therefore the file will only be shared (and not downloaded)
    :param resource: the resource class representing the class to be uploaded/downloaded
    """
    ...
```
## Public methods:
### The most useful ones:
```python
async def full_start(
        self,
        restore_previous=True,
        start_sharing_file=True,
        start_download=True,
        open_public_port=True
) -> int | None:
    """
    A method to start the `ResourceManager`. Clients MUST call this method in order to fully start the `ResourceManager`.
    The method has a bunch of flags that allow clients to adjust the parameters of `ResourceManager`
    at the beginning. Any disabled flag can be enabled later by calling the appropriate public method.

    The method is not guaranteed to be idempotent (i.e. repeating calls of `full_start()` to the
    running ResourceManager may cause exceptions/various errors).

    :return: if `open_public_port` is True then  the return value is the same as `open_public_port()` otherwise None
    """
```
```python
async def shutdown(self):
    """
    A method to stop the running `ResourceManager`. The clients MUST call this method in order to fully stop the
    running `ResourceManager` and release all associated resources.

    The method is idempotent (repeating calls do not cause any errors/exception)
    """
    ...
```
```python
async def submit_peers(self, peers: list[PeerInfo]):
    """
    The only way to tell ResourceManager about peers related to the resource. Usually these will be peers fetched
    from the tracker response on announce request with the *same* info hash as the RequestManager was created with.

    :param peers: The list of peers known to be related with the resource
    """
    ...
```
```python
async def get_state(self) -> 'ResourceManager.State':
    """
    Get the current state of the resource (i.e. downloaded pieces, upload/download speed etc.)
    :return: The current state of the resource (file)
    """
    ...
```

### The rest public methods:
```python
async def open_public_port(self) -> int:
    """
    Opens a new socket that will be used to accept incoming connections from other peers

    :return: port on which the new socket is opened
    """
    ...
```
```python
async def close_public_port(self):
    """
    Closes the socket that accepts the new connections (NOTE: after calling this method, the old port received in
    `open_public_port` cannot be reused anymore as this port is received randomly from the OS)
    """
    ...
```
```python
async def restore_previous(self):
    """
    Attempts to restore the saved state and start download with this state (for example, to get which pieces
    are already downloaded in order to not repeat the download work).

    NOTE: If the destination file exists, then this method
    assumes that the file is already completely downloaded
    (and so sets the status of all pieces as SAVED (or downloaded))
    """
    ...
```
```python
async def start_download(self):
    """
    Start downloading the file. If the destination file already exists, then this method does nothing. The file
    will usually be downloaded into a specifically named temporary file located at the same folder as `destination`.
    Once the ResourceManager detects, that the file is completely downloaded
    it terminates the download and renames the temporary file into the `destination`.
    """
    ...
```
```python
async def stop_download(self):
    """
    Stop downloading the file.
    """
    ...
```
```python
async def start_sharing_file(self):
    """
    Sets the flags that allows ResourceManager to share file (file pieces) with other peers.
    This is the default behaviour.
    """
    ...
```
```python
async def stop_sharing_file(self):
    """
    Forbid the ResourceManager to share file (file pieces) with other peers.
    """
    ...
```