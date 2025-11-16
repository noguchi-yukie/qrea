(() => {
  const scriptEl = document.getElementById('scan-script');
  const mode = scriptEl?.dataset?.mode || window.qrMode || 'assign';
  const videoEl = document.getElementById('scan-video');
  const startBtn = document.getElementById('scan-start');
  const stopBtn = document.getElementById('scan-stop');
  const fileInput = document.getElementById('scan-file');
  const statusEl = document.getElementById('scan-status');

  if (!videoEl || !startBtn || !stopBtn || !statusEl) {
    return;
  }

  // Legacy getUserMedia polyfill (for older Safari / Android WebView)
  const legacyGetUserMedia =
    navigator.getUserMedia ||
    navigator.webkitGetUserMedia ||
    navigator.mozGetUserMedia ||
    navigator.msGetUserMedia;
  if (typeof navigator.mediaDevices === 'undefined') {
    navigator.mediaDevices = {};
  }
  if (!navigator.mediaDevices.getUserMedia && legacyGetUserMedia) {
    navigator.mediaDevices.getUserMedia = (constraints) =>
      new Promise((resolve, reject) => legacyGetUserMedia.call(navigator, constraints, resolve, reject));
  }

  let reader = null;
  let controls = null;
  let isRunning = false;

  const ZX = window.ZXing;

  function setStatus(text) {
    statusEl.textContent = text;
  }

  function ensureReader() {
    if (!ZX || !ZX.BrowserMultiFormatReader) {
      setStatus('ZXingライブラリを読み込めませんでした。ページを再読み込みしてください。');
      return null;
    }
    if (!reader) {
      reader = new ZX.BrowserMultiFormatReader();
    }
    return reader;
  }

  function extractQrId(raw) {
    if (!raw) return '';
    const trimmed = raw.trim();
    try {
      const url = new URL(trimmed);
      const queryId = url.searchParams.get('qr_id') || url.searchParams.get('id');
      if (queryId) return queryId;
      const segments = url.pathname.split('/').filter(Boolean);
      if (segments.length) return segments.pop();
    } catch (e) {
      // not a URL, ignore
    }
    return trimmed;
  }

  function handleDecodedText(text) {
    const qrId = extractQrId(text);
    if (qrId) {
      navigateTo(qrId);
    } else {
      setStatus('QRコードは検出されましたがIDを抽出できませんでした。');
    }
  }

  function navigateTo(qrId) {
    const target = mode === 'return'
      ? `/return/${encodeURIComponent(qrId)}`
      : `/assign/${encodeURIComponent(qrId)}`;
    setStatus(`検出: ${qrId} に移動します…`);
    setTimeout(() => {
      window.location.href = target;
    }, 600);
  }

  function hasCameraSupport() {
    return !!(navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === 'function');
  }

  async function startScan() {
    if (isRunning) return;
    if (!hasCameraSupport()) {
      setStatus('このブラウザーはリアルタイムカメラに対応していません。画像取り込みで読み取ってください。');
      return;
    }
    const readerInstance = ensureReader();
    if (!readerInstance) return;

    isRunning = true;
    startBtn.disabled = true;
    stopBtn.disabled = false;
    setStatus('カメラを初期化しています…');

    try {
      await readerInstance.decodeFromVideoDevice(null, videoEl, (result, err, ctrl) => {
        if (ctrl) {
          controls = ctrl;
        }
        if (result) {
          const text = result.getText ? result.getText() : result.text;
          stopScan();
          handleDecodedText(text);
          return;
        }
        if (err) {
          const ignorable = ['NotFoundException', 'ChecksumException', 'FormatException', 'NotFoundError'];
          if (!ignorable.includes(err.name)) {
            console.warn(err);
          }
        }
      });
      setStatus('読み取り中…');
    } catch (error) {
      console.error(error);
      setStatus(`カメラを起動できません: ${error?.message || error}`);
      stopScan();
    }
  }

  function stopScan() {
    if (!isRunning && !controls) {
      return;
    }
    isRunning = false;
    if (controls && typeof controls.stop === 'function') {
      controls.stop();
    }
    controls = null;
    if (reader) {
      reader.reset();
    }
    if (videoEl.srcObject && typeof videoEl.srcObject.getTracks === 'function') {
      videoEl.srcObject.getTracks().forEach((track) => track.stop());
    }
    videoEl.srcObject = null;
    startBtn.disabled = false;
    stopBtn.disabled = true;
    setStatus('停止しました。再度カメラを起動できます。');
  }

  startBtn.addEventListener('click', (event) => {
    event.preventDefault();
    startScan();
  });

  stopBtn.addEventListener('click', (event) => {
    event.preventDefault();
    stopScan();
  });

  function readFileAsDataURL(file) {
    return new Promise((resolve, reject) => {
      const readerInstance = new FileReader();
      readerInstance.onload = () => resolve(readerInstance.result);
      readerInstance.onerror = reject;
      readerInstance.readAsDataURL(file);
    });
  }

  async function decodeImageFile(file) {
    if (!file) return;
    if (!ZX || !ZX.BrowserMultiFormatReader) {
      setStatus('ZXingライブラリを読み込めませんでした。ページを再読み込みしてください。');
      return;
    }
    setStatus('画像を解析しています…');
    try {
      const bitmap = await createImageBitmap(file);
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      const maxLength = 1080;
      const scale = Math.min(1, maxLength / Math.max(bitmap.width, bitmap.height));
      canvas.width = Math.max(1, Math.floor(bitmap.width * scale));
      canvas.height = Math.max(1, Math.floor(bitmap.height * scale));
      ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);

      let binaryBitmap;
      if (ZX.HTMLCanvasElementLuminanceSource && ZX.BinaryBitmap && ZX.HybridBinarizer) {
        const luminance = new ZX.HTMLCanvasElementLuminanceSource(canvas);
        binaryBitmap = new ZX.BinaryBitmap(new ZX.HybridBinarizer(luminance));
      } else if (ZX.BinaryBitmap && ZX.HybridBinarizer && ZX.RGBLuminanceSource) {
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const luminance = new ZX.RGBLuminanceSource(imageData.data, canvas.width, canvas.height);
        binaryBitmap = new ZX.BinaryBitmap(new ZX.HybridBinarizer(luminance));
      } else if (ZX.BinaryBitmap && ZX.LuminanceSource) {
        const luminance = ZX.LuminanceSource.createLuminanceSource(canvas);
        binaryBitmap = new ZX.BinaryBitmap(new ZX.HybridBinarizer(luminance));
      } else {
        throw new Error('ZXingのイメージ解析APIが利用できません');
      }

      const hints = new Map();
      if (ZX.DecodeHintType) {
        hints.set(ZX.DecodeHintType.TRY_HARDER, true);
      }
      const reader = new ZX.BrowserMultiFormatReader(hints);
      const result = reader.decode(binaryBitmap);
      const text = result.getText ? result.getText() : result.text;
      handleDecodedText(text);
    } catch (error) {
      console.error(error);
      setStatus(`画像から読み取れませんでした (${error?.message || error}).`);
    }
  }

  if (fileInput) {
    fileInput.addEventListener('change', (event) => {
      const file = event.target.files?.[0];
      decodeImageFile(file);
      // reset so same file can be selected again
      event.target.value = '';
    });
  }

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      stopScan();
    }
  });
})();
