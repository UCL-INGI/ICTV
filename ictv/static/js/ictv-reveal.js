function initCustom(controls, slideNumber, width, height){
    controls = controls === undefined ? true : controls;
    Reveal.addEventListener('slidechanged', onSlideReady);
    Reveal.addEventListener('ready', onSlideReady);
    Reveal.initialize({
        width: width,
        height: height,
        controls: controls,
        slideNumber: slideNumber,
        minScale: 0.2,
        maxScale: 1.5,
        transitionSpeed: 'slowest',
        progress: false
    });
}

function init(controls, slideNumber) {
    initCustom(controls, slideNumber, 1600, 900);
}

function initPortrait(controls, slideNumber) {
    initCustom(controls, slideNumber, 900, 1600);
}

function onSlideReady(event) {
    $(event.currentSlide).find('img').waitForImages(true).done(function() {
        setTimeout(function () {
            setImages($(event.currentSlide), true);
        }, 1)
    })
}

function setImages($slide, force) {
    if (force || ($slide.find(".content")[0] && !$slide.find(".content")[0].style['margin-top'])) {
        var top = $slide[0].style.top;
        $slide[0].style.top = "0px";
        $slide.find(".content")[0].style['margin-top'] = top;
    }
}