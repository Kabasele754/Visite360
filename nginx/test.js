var ws = new WebSocket('wss://s4e-elevatai.com/ws/location/site/1/');
ws.onopen = function() {
    console.log('WebSocket connection opened.');
};
ws.onerror = function(error) {
    console.error('WebSocket error:', error);
};
ws.onclose = function() {
    console.log('WebSocket connection closed.');
};
