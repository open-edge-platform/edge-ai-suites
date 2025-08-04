/* Get name of this js file */
function getScriptName() {
    var error = new Error()
      , source
      , lastStackFrameRegex = new RegExp(/.+\/(.*?):\d+(:\d+)*$/)
      , currentStackFrameRegex = new RegExp(/getScriptName \(.+\/(.*):\d+:\d+\)/);

    if((source = lastStackFrameRegex.exec(error.stack.trim())) && source[1] != "")
        return source[1];
    else if((source = currentStackFrameRegex.exec(error.stack.trim())))
        return source[1];
    else if(error.fileName != undefined)
        return error.fileName;
}

/* Always link logo to index.html */
$(document).ready(function(){
    var name = getScriptName().split(".js")[0]
    var base = $('script[src*='+name+']').attr('src').split("_static")[0]
    $( ".icon-home" ).attr( "href", base + "index.html");
});

/* Open external links in new tab */ 
$(document).ready(function () {
   $('a[href^="http://"], a[href^="https://"]').not('a[class*=internal]').attr('target', '_blank');
});

/* Add color modification */
/* bg = background */
/* d_ = dark color */
/* l_ = light color */
/* r = red; o = orange; g = green; b = blue; y = yellow; p = purple; t = cyan; w = white */

$(document).ready(function() {
    $('.bgdr').parent().parent().addClass('bgdr-parent');
    $('.bglr').parent().parent().addClass('bglr-parent');
    $('.bgdo').parent().parent().addClass('bgdo-parent');
    $('.bglo').parent().parent().addClass('bglo-parent');
    $('.bgdg').parent().parent().addClass('bgdg-parent');
    $('.bglg').parent().parent().addClass('bglg-parent');
    $('.bgdb').parent().parent().addClass('bgdb-parent');
    $('.bglb').parent().parent().addClass('bglb-parent');
    $('.bgdy').parent().parent().addClass('bgdy-parent');
    $('.bgly').parent().parent().addClass('bgly-parent');
    $('.bgdp').parent().parent().addClass('bgdp-parent');
    $('.bglp').parent().parent().addClass('bglp-parent');
    $('.bgdc').parent().parent().addClass('bgdc-parent');
    $('.bglc').parent().parent().addClass('bglc-parent');
    $('.bgd').parent().parent().addClass('bgd-parent');
    $('.bgl').parent().parent().addClass('bgl-parent');
    $('.bgw').parent().parent().addClass('bgw-parent');
    $('.rowtitle').parent().parent().addClass('rowtitle');
});

