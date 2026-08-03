import * as pdfjsLib from "/assets/pdfjs/build/pdf.mjs";

pdfjsLib.GlobalWorkerOptions.workerSrc = "/assets/pdfjs/build/pdf.worker.mjs";

const params = new URLSearchParams(window.location.search);
const fileUrl = params.get("file");
const viewer = document.getElementById("viewer");

let pdfDoc = null;
let resizeTimer = null;

function showError(message) {
  viewer.innerHTML = `<div class="error">${message}</div>`;
}

async function renderPdf() {
  if (!pdfDoc) return;

  viewer.innerHTML = "";

  const availableWidth = Math.min(viewer.clientWidth - 32, 1100);
  const outputScale = window.devicePixelRatio || 1;

  for (let pageNum = 1; pageNum <= pdfDoc.numPages; pageNum++) {
    const page = await pdfDoc.getPage(pageNum);

    const baseViewport = page.getViewport({ scale: 1 });
    const scale = availableWidth / baseViewport.width;
    const viewport = page.getViewport({ scale });

    const pageWrapper = document.createElement("div");
    pageWrapper.className = "page";

    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");

    canvas.width = Math.floor(viewport.width * outputScale);
    canvas.height = Math.floor(viewport.height * outputScale);
    canvas.style.width = `${Math.floor(viewport.width)}px`;
    canvas.style.height = `${Math.floor(viewport.height)}px`;

    pageWrapper.appendChild(canvas);
    viewer.appendChild(pageWrapper);

    const transform =
      outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : null;

    await page.render({
      canvasContext: ctx,
      viewport,
      transform,
    }).promise;
  }
}

async function loadPdf(url) {
  try {
    const loadingTask = pdfjsLib.getDocument({ url: decodeURIComponent(url) });
    pdfDoc = await loadingTask.promise;
    await renderPdf();
  } catch (err) {
    console.error("PDF load error:", err);
    showError(`Could not load the PDF: ${err?.message || err}`);
  }
}

const observer = new ResizeObserver(() => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    renderPdf();
  }, 150);
});

observer.observe(viewer);

if (!fileUrl) {
  showError("Missing ?file= parameter.");
} else {
  loadPdf(fileUrl);
}
