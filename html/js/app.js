


let auto_scroll = true;
var ws = new WebSocket("ws://localhost:3939/websocket");


let scrollId = 2;
$("#output").scroll(function() {
    auto_scroll = false;
    window.clearTimeout(scrollId);
    scrollId = window.setTimeout(function(){
        auto_scroll = true;
    }, 3000);
});


window.onbeforeunload = function() {
    console.log("close session");
    ws.send(JSON.stringify({"msg":"close"}));
    ws.close();
};



ws.onerror = function(event) {
    console.error("WebSocket error observed");
    $("#status").css("color", "tomato").text("SERVER ERROR");
    clearInterval(timerId);
}


ws.onopen = function() {
    console.log("send message");
    $("#status").css("color", "chartreuse").text("SUCCESS CONNECTION");
    timerId = setInterval(function(){
        ws.send(JSON.stringify({"msg":"request"}));
    }, 100);
};


let current_num_sentences = 0;
let cursor = -1;
ws.onmessage = function (evt) {
    cursor++;
    let response = JSON.parse(evt.data);
    //console.log(response);
    let start_idx = response["start_idx"];
    let source = response["source"];
    let target_g = response["target"];
    let N = source.length;
    if (auto_scroll == true) {
        let objDiv = document.getElementById("output");
        objDiv.scrollTop = objDiv.scrollHeight;
    }
    let total_sentences = start_idx + N;
    if (current_num_sentences < total_sentences) {
        for (let i in source) {
            let idx = start_idx + parseInt(i);
            if (idx < current_num_sentences) {
                $("#text_" + idx + ">.source").text(source[i]);
                $("#text_" + idx + ">.target_g").text(target_g[i]);
                continue;
            }
            let $text = $("<div/>").addClass("text").attr("id", "text_"+idx);
            $("<div/>").addClass("source").text(source[i]).appendTo($text);
            $("<div/>").addClass("target_g").css("display", "block").text(target_g[i]).appendTo($text);
            $("<div/>").addClass("target_d").css("display", "none").appendTo($text);
            $text.appendTo("#output")
            current_num_sentences++;
        }
    } else {

        for (let i in source) {
            let idx = start_idx + parseInt(i);
            $("#text_" + idx + ">.source").text(source[i]);
            $("#text_" + idx + ">.target_g").text(target_g[i]);
        }

    }

    if (cursor % 20 == 0) {
        let text = source.join("\n\n");
        let _start_idx = start_idx;
        if (text.length > 0) {
            $.ajax({
                type: "post", 
                url: '//' + location.host + '/api/translate',
                dataType:'json',
                data: {"text":text, "source_lang":"EN", "target_lang":"JA"}, 
                success: function(json) {
                    translate_text_d = json["translation"].split("\n\n");
                    for (let j in translate_text_d) {
                        let _idx = _start_idx + parseInt(j);
                        $("#text_" + _idx + ">.target_d").css("display", "block").text(translate_text_d[j]);
                    }
                }, 
                error:function() {
                }
            });
        }
    }
};


ws.onclose = function () {
    clearInterval(timerId);
}




