// languages

const translations = {
  en: {
    title: "Crop Price Prediction",
    language: "Language",
    crop: "Crop Name",
    weather: "Weather Data",
    live: "Use My Live Location",
    manual: "Enter Manually",
    predict: "Predict Price"
  },
  kn: {
    title: "ಬೆಳೆ ಬೆಲೆ ಮುನ್ಸೂಚನೆ",
    language: "ಭಾಷೆ",
    crop: "ಬೆಳೆ ಹೆಸರು",
    weather: "ಹವಾಮಾನ ಮಾಹಿತಿ",
    live: "ನನ್ನ ಸ್ಥಳ ಬಳಸಿ",
    manual: "ಹಸ್ತಚಾಲಿತವಾಗಿ ನಮೂದಿಸಿ",
    predict: "ಬೆಲೆ ತಿಳಿಯಿರಿ"
  }
}

function changeLanguage() {
  const lang = document.getElementById("language").value
  const t = translations[lang]
  document.getElementById("title").innerText = t.title
  document.getElementById("label-language").innerText = t.language
  document.getElementById("label-crop").innerText = t.crop
  document.getElementById("label-weather").innerText = t.weather
  document.getElementById("btn-live").innerText = "📍 " + t.live
  document.getElementById("btn-manual").innerText = "✏️ " + t.manual
  document.getElementById("predict-btn").innerText = t.predict
}


// crop suggestions

const crops = [
  "Tomato","Onion","Potato","Rice","Wheat",
  "Bajra","Maize","Soybean","Cotton","Sugarcane"
]

const cropInput = document.getElementById("crop-input")
const suggBox   = document.getElementById("crop-suggestions")

cropInput.addEventListener("input", () => {
  const value = cropInput.value.toLowerCase()
  suggBox.innerHTML = ""
  if (!value) { suggBox.style.display = "none"; return }

  const matches = crops.filter(c => c.toLowerCase().includes(value))
  matches.forEach(c => {
    const div = document.createElement("div")
    div.className = "suggestion-item"
    div.innerText = c
    div.onclick = () => { cropInput.value = c; suggBox.style.display = "none" }
    suggBox.appendChild(div)
  })
  suggBox.style.display = matches.length ? "block" : "none"
})


// weather

let weatherData = null

// Fetch weather with a 6-second timeout to avoid hanging
async function fetchWithTimeout(url, ms = 6000) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), ms)
  try {
    const res = await fetch(url, { signal: controller.signal })
    clearTimeout(timer)
    return res
  } catch (e) {
    clearTimeout(timer)
    throw e
  }
}

function setLocationStatus(msg, isError = false) {
  const el = document.getElementById("location-status")
  el.innerText = msg
  el.style.color = isError ? "#c0392b" : "#27ae60"
}

async function useLiveLocation() {
  const btn = document.getElementById("btn-live")
  btn.disabled = true
  btn.innerText = "⏳ Fetching..."
  setLocationStatus("Getting location...")

  navigator.geolocation.getCurrentPosition(
    async pos => {
      const { latitude: lat, longitude: lon } = pos.coords
      const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,relative_humidity_2m,precipitation`

      try {
        const res  = await fetchWithTimeout(url, 6000)
        const data = await res.json()
        weatherData = {
          temperature: data.current.temperature_2m,
          humidity:    data.current.relative_humidity_2m,
          rainfall:    data.current.precipitation
        }
        setLocationStatus(`🌡 ${weatherData.temperature}°C  💧 ${weatherData.humidity}%`)
        document.getElementById("manual-fields").style.display = "none"
      } catch {
        setLocationStatus("Weather fetch timed out — enter manually", true)
        useManual()
      }
      btn.disabled = false
      btn.innerText = "📍 Use My Live Location"
    },
    err => {
      setLocationStatus("Location denied — enter manually", true)
      useManual()
      btn.disabled = false
      btn.innerText = "📍 Use My Live Location"
    },
    { timeout: 8000 }   // geolocation timeout
  )
}

function useManual() {
  document.getElementById("manual-fields").style.display = "block"
  weatherData = null
}


// predict

async function predictPrice() {
  const crop = cropInput.value.trim()
  if (!crop) { alert("Please enter a crop name"); return }

  const btn = document.getElementById("predict-btn")
  btn.disabled = true
  btn.innerText = "⏳ Predicting..."

  let rainfall, temperature, humidity

  if (weatherData) {
    rainfall    = weatherData.rainfall
    temperature = weatherData.temperature
    humidity    = weatherData.humidity
  } else {
    rainfall    = document.getElementById("rainfall").value
    temperature = document.getElementById("temperature").value
    humidity    = document.getElementById("humidity").value
  }

  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 10000)  // 10s timeout

    const res = await fetch("http://127.0.0.1:5000/predict", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      signal:  controller.signal,
      body:    JSON.stringify({ crop, rainfall, temperature, humidity })
    })
    clearTimeout(timer)

    const data = await res.json()

    if (data.error) {
      alert("Error: " + data.error)
    } else {
      const sourceLabel = { model: "ML Model", live: "Live Mandi", fallback: "Avg Market" }
      alert(`Predicted price: ₹${data.price}/quintal\nSource: ${sourceLabel[data.source] || data.source}`)
    }
  } catch (e) {
    if (e.name === "AbortError") {
      alert("Request timed out. Please try again.")
    } else {
      alert("Could not connect to server. Is the backend running?")
    }
  }

  btn.disabled = false
  btn.innerText = document.getElementById("language").value === "kn"
    ? translations.kn.predict
    : translations.en.predict
}