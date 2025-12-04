// Global state
let currentNetworks = []

// Tab switching
function switchTab(tabName) {
  // Update tab buttons
  document.querySelectorAll('.tab').forEach((tab) => tab.classList.remove('active'))
  event.target.classList.add('active')

  // Update tab content
  document.querySelectorAll('.tab-content').forEach((content) => content.classList.remove('active'))

  if (tabName === 'wifi') {
    document.getElementById('wifiTab').classList.add('active')
  } else if (tabName === 'system') {
    document.getElementById('systemTab').classList.add('active')
    loadAPInfo()
  }
}

// System Tab - AP Management
async function loadAPInfo() {
  try {
    let res = await fetch('/api/ap-info')
    let data = await res.json()

    const apInfoEl = document.getElementById('apInfo')

    if (data.ok) {
      apInfoEl.innerHTML = `<strong>Current AP:</strong> ${data.ssid})`
    } else {
      apInfoEl.innerHTML = 'Failed to load AP info'
    }
  } catch (e) {
    console.error('Failed to load AP info:', e)
    document.getElementById('apInfo').innerHTML = 'Error loading AP info'
  }
}

function toggleAPPassword() {
  const pwdInput = document.getElementById('apPasswordInput')
  const eyeOpen = document.querySelector('.eye-open-ap')
  const eyeClosed = document.querySelector('.eye-closed-ap')
  if (pwdInput.type === 'password') {
    pwdInput.type = 'text'
    eyeOpen.style.display = 'none'
    eyeClosed.style.display = 'block'
  } else {
    pwdInput.type = 'password'
    eyeOpen.style.display = 'block'
    eyeClosed.style.display = 'none'
  }
}

async function changeAPPassword() {
  const apPasswordInput = document.getElementById('apPasswordInput')
  const changeAPPasswordBtn = document.getElementById('changeAPPasswordBtn')
  const apResultEl = document.getElementById('apResult')
  const apErrorEl = document.getElementById('apError')
  const apSuccessEl = document.getElementById('apSuccess')

  // Clear messages
  apResultEl.innerText = ''
  apErrorEl.innerText = ''
  apSuccessEl.innerText = ''
  apErrorEl.style.animation = 'none'
  apSuccessEl.style.animation = 'none'
  void apErrorEl.offsetWidth
  void apSuccessEl.offsetWidth

  const password = apPasswordInput.value.trim()

  // Client-side validation
  if (!password) {
    apErrorEl.innerHTML = 'Please enter a password'
    apErrorEl.className = 'err'
    apErrorEl.style.animation = 'fadeIn 0.5s forwards'
    return
  }

  if (password.length < 8) {
    apErrorEl.innerHTML = 'Password must be at least 8 characters'
    apErrorEl.className = 'err'
    apErrorEl.style.animation = 'fadeIn 0.5s forwards'
    return
  }

  if (password.length > 63) {
    apErrorEl.innerHTML = 'Password must not exceed 63 characters'
    apErrorEl.className = 'err'
    apErrorEl.style.animation = 'fadeIn 0.5s forwards'
    return
  }

  // Check for dangerous characters
  const dangerousChars = /[`$\\\n\r\0]/
  if (dangerousChars.test(password)) {
    apErrorEl.innerHTML = 'Password contains invalid characters (`, $, \\\\)'
    apErrorEl.className = 'err'
    apErrorEl.style.animation = 'fadeIn 0.5s forwards'
    return
  }

  changeAPPasswordBtn.disabled = true
  changeAPPasswordBtn.classList.add('loading')
  changeAPPasswordBtn.querySelector('span').innerText = 'Changing...'

  try {
    let res = await fetch('/api/change-ap-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    })

    let data = await res.json()

    if (data.ok) {
      apSuccessEl.innerHTML = '✓ AP password changed successfully!'
      apSuccessEl.style.animation = 'fadeIn 0.5s forwards'
      apPasswordInput.value = ''
    } else {
      apErrorEl.innerHTML = data.error || 'Failed to change password'
      apErrorEl.className = 'err'
      apErrorEl.style.animation = 'fadeIn 0.5s forwards'
    }
  } catch (e) {
    apErrorEl.innerHTML = 'Error changing password'
    apErrorEl.className = 'err'
    apErrorEl.style.animation = 'fadeIn 0.5s forwards'
  } finally {
    changeAPPasswordBtn.disabled = false
    changeAPPasswordBtn.classList.remove('loading')
    changeAPPasswordBtn.querySelector('span').innerText = 'Change Password'
  }
}

// WiFi Tab - Connection Management
async function loadCurrentConnection() {
  try {
    let res = await fetch('/api/current-connection')
    let data = await res.json()

    const container = document.getElementById('currentConnection')

    if (data.ok && data.connected) {
      const signalIcon = createSignalIcon(data.signal)
      container.innerHTML = `
        <div class="current-connection">
          <div class="current-connection-info">
            <div class="current-connection-icon">✓</div>
            <div class="current-connection-text">
              <div class="current-connection-ssid">${data.ssid}</div>
              <div class="current-connection-status">Connected • ${data.interface}</div>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 6px;">
            ${signalIcon}
            <button class="disconnect-btn" onclick="showDisconnectModal()" title="Disconnect">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M19 13H5v-2h14v2z" fill="currentColor"/>
              </svg>
            </button>
          </div>
        </div>
      `
      container.style.display = 'block'
    } else {
      container.style.display = 'none'
    }
  } catch (e) {
    console.error('Failed to load current connection:', e)
  }
}

async function loadSavedNetworks() {
  try {
    let res = await fetch('/api/saved-networks')
    let data = await res.json()

    const section = document.getElementById('savedNetworksSection')
    const list = document.getElementById('savedNetworksList')

    if (data.ok && data.networks && data.networks.length > 0) {
      list.innerHTML = data.networks
        .map(
          (net) => `
        <div class="saved-network">
          <div class="saved-network-name">${net.ssid}</div>
          <button class="forget-btn" onclick="forgetNetwork('${net.ssid.replace(/'/g, "\\'")}')">Forget</button>
        </div>
      `
        )
        .join('')
      section.style.display = 'block'
    } else {
      section.style.display = 'none'
    }
  } catch (e) {
    console.error('Failed to load saved networks:', e)
  }
}

async function forgetNetwork(ssid) {
  if (!confirm(`Forget network "${ssid}"?`)) return

  try {
    let res = await fetch('/api/forget-network', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ssid }),
    })

    let data = await res.json()

    if (data.ok) {
      await loadSavedNetworks()
      await loadCurrentConnection()
    } else {
      alert('Failed to forget network: ' + (data.error || 'Unknown error'))
    }
  } catch (e) {
    alert('Error forgetting network')
  }
}

async function disconnectCurrent() {
  try {
    let res = await fetch('/api/disconnect-current', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })

    let data = await res.json()

    if (data.ok) {
      // Close modal
      closeDisconnectModal()
      
      // Reload both current connection and saved networks
      await loadCurrentConnection()
      await loadSavedNetworks()
      
      // Show success message
      const successEl = document.getElementById('success')
      successEl.innerHTML = '✓ Disconnected successfully'
      successEl.style.animation = 'fadeIn 0.5s forwards'
      
      setTimeout(() => {
        successEl.style.animation = 'fadeOut 0.5s forwards'
      }, 3000)
    } else {
      closeDisconnectModal()
      alert('Failed to disconnect: ' + (data.error || 'Unknown error'))
    }
  } catch (e) {
    closeDisconnectModal()
    alert('Error disconnecting from network')
  }
}

function showDisconnectModal() {
  const modal = document.getElementById('disconnectModal')
  modal.style.display = 'flex'
  // Trigger animation
  setTimeout(() => {
    modal.classList.add('active')
  }, 10)
}

function closeDisconnectModal() {
  const modal = document.getElementById('disconnectModal')
  modal.classList.remove('active')
  setTimeout(() => {
    modal.style.display = 'none'
  }, 200)
}

// Utility functions
function clearMessages() {
  const errorEl = document.getElementById('error')
  const successEl = document.getElementById('success')
  const resultEl = document.getElementById('result')
  errorEl.innerText = ''
  successEl.innerText = ''
  resultEl.innerText = ''
  errorEl.style.animation = 'none'
  successEl.style.animation = 'none'
  errorEl.className = ''

  void errorEl.offsetWidth
  void successEl.offsetWidth
}

function getSignalBars(signal) {
  if (!signal) return 1
  if (signal >= 80) return 4
  if (signal >= 60) return 3
  if (signal >= 40) return 2
  return 1
}

function createSignalIcon(signal) {
  const bars = getSignalBars(signal)
  let html = '<div class="signal-strength">'
  for (let i = 0; i < 4; i++) {
    const height = 4 + i * 3
    const isActive = i < bars
    html += `<div class="signal-bar ${isActive ? 'active' : ''}" style="height: ${height}px;"></div>`
  }
  html += '</div>'
  return html
}

function removeDuplicateNetworks(networks) {
  const uniqueNetworks = []
  const seenSSIDs = new Set()

  for (const network of networks) {
    if (!seenSSIDs.has(network.ssid)) {
      seenSSIDs.add(network.ssid)
      uniqueNetworks.push(network)
    }
  }

  return uniqueNetworks
}

// WiFi scanning
async function scan() {
  clearMessages()
  const scanBtn = document.getElementById('scanBtn')
  const ssidList = document.getElementById('ssidList')
  const scanningOverlay = document.getElementById('scanningOverlay')

  scanBtn.disabled = true
  scanBtn.classList.add('loading')
  ssidList.classList.add('scanning')
  scanningOverlay.classList.add('active')

  try {
    await new Promise((resolve) => setTimeout(resolve, 600))

    let res = await fetch('/api/scan')
    let data = await res.json()

    // Remove duplicate networks before storing
    currentNetworks = removeDuplicateNetworks(data.networks || [])

    let list = ''
    if (currentNetworks.length > 0) {
      for (let n of currentNetworks) {
        const signalIcon = createSignalIcon(n.signal)
        list += `
          <div class="ssid" onclick="selectSSID('${n.ssid.replace(/'/g, "\\'")}')">
            <div class="ssid-info">
              <b>${n.ssid}</b>
            </div>
            ${signalIcon}
          </div>`
      }
      ssidList.innerHTML = list
    } else {
      ssidList.innerHTML = '<div class="empty-state">No networks found. Try again.</div>'
    }
  } catch (e) {
    console.error('Scan error:', e)
    ssidList.innerHTML = '<div class="empty-state">Unable to scan Wi-Fi networks</div>'
  } finally {
    scanBtn.disabled = false
    scanBtn.classList.remove('loading')
    ssidList.classList.remove('scanning')
    scanningOverlay.classList.remove('active')

    // Refresh connection status after scan
    loadCurrentConnection()
    loadSavedNetworks()
  }
}

function selectSSID(ssid) {
  document.getElementById('ssidInput').value = ssid
  document.getElementById('pwdInput').focus()
}

function togglePassword() {
  const pwdInput = document.getElementById('pwdInput')
  const eyeOpen = document.querySelector('.eye-open')
  const eyeClosed = document.querySelector('.eye-closed')
  if (pwdInput.type === 'password') {
    pwdInput.type = 'text'
    eyeOpen.style.display = 'none'
    eyeClosed.style.display = 'block'
  } else {
    pwdInput.type = 'password'
    eyeOpen.style.display = 'block'
    eyeClosed.style.display = 'none'
  }
}

// WiFi connection
async function connect() {
  clearMessages()
  const connectBtn = document.getElementById('connectBtn')
  const resultEl = document.getElementById('result')

  const ssid = document.getElementById('ssidInput').value.trim()
  const password = document.getElementById('pwdInput').value.trim()

  if (!ssid) {
    const errorEl = document.getElementById('error')
    errorEl.innerHTML = 'Please enter a network name'
    errorEl.className = 'err'
    errorEl.style.animation = 'fadeIn 0.5s forwards'
    return
  }

  connectBtn.disabled = true
  connectBtn.classList.add('loading')
  connectBtn.querySelector('span').innerText = 'Connecting'

  try {
    let res = await fetch('/api/connect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ssid, password }),
    })

    let data = await res.json()

    if (res.status === 200 && data.ok) {
      window.location.href = '/success.html'
    } else {
      const errorEl = document.getElementById('error')
      const errorMsg = data.error || 'Unable to join this network. Please try again.'
      errorEl.innerHTML = `${errorMsg}`
      errorEl.className = 'err'
      errorEl.style.animation = 'fadeIn 0.5s forwards'
      resultEl.innerText = ''
    }
  } catch (e) {
    const errorEl = document.getElementById('error')
    errorEl.innerHTML = 'Connection failed. Please try again.'
    errorEl.className = 'err'
    errorEl.style.animation = 'fadeIn 0.5s forwards'
    resultEl.innerText = ''
  } finally {
    connectBtn.disabled = false
    connectBtn.classList.remove('loading')
    connectBtn.querySelector('span').innerText = 'Connect'
  }
}

// Initialize app
document.addEventListener('DOMContentLoaded', function () {
  document.getElementById('scanBtn').onclick = scan
  document.getElementById('connectBtn').onclick = connect
  document.getElementById('changeAPPasswordBtn').onclick = changeAPPassword

  // Load initial data
  loadCurrentConnection()
  loadSavedNetworks()
  scan()

  document.getElementById('pwdInput').addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
      connect()
    }
  })

  document.getElementById('apPasswordInput').addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
      changeAPPassword()
    }
  })
})
