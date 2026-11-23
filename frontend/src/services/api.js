import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  // tells the backend this is a current UI build (see evict_stale_ui in main.py)
  config.headers['X-UI-Build'] = '1'
  return config
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401
      && !location.pathname.startsWith('/login')
      && !location.pathname.startsWith('/register')) {
      localStorage.removeItem('token')
      location.href = '/login'
    }
    return Promise.reject(err)
  },
)

export const AuthAPI = {
  login: (username, password) => {
    const body = new URLSearchParams({ username, password })
    return api.post('/auth/login', body)
  },
  logout: () => api.post('/auth/logout'),
  me: () => api.get('/auth/me'),
  register: (username, password) => api.post('/auth/register', { username, password }),
}

export const DeviceAPI = {
  list: () => api.get('/devices'),
  create: (d) => api.post('/devices', d),
  update: (id, d) => api.put(`/devices/${id}`, d),
  remove: (id) => api.delete(`/devices/${id}`),
  status: (id) => api.post(`/devices/${id}/status`),
  refreshAll: () => api.post('/devices/status/refresh-all'),
  dhcpScopes: () => api.get('/devices/dhcp/scopes'),
  requestDhcp: (id, subnet) => api.post(`/devices/${id}/dhcp`, { subnet: subnet ?? null }),
  releaseDhcp: (id) => api.delete(`/devices/${id}/dhcp`),
  config: (id) => api.get(`/devices/${id}/config`),
  vlans: (id) => api.get(`/devices/${id}/vlans`),
  interfaces: (id) => api.get(`/devices/${id}/interfaces`),
}

export const TopologyAPI = {
  graph: () => api.get('/topology'),
  deviceInfo: (id) => api.get(`/topology/devices/${id}/info`),
  addLink: (d) => api.post('/topology/connections', d),
  removeLink: (id) => api.delete(`/topology/connections/${id}`),
  move: (id, x, y) => api.patch(`/topology/devices/${id}/position`, { x, y }),
}

export const SmartAPI = {
  preview: (d) => api.post('/smart-config/preview', d),
  run: (d) => api.post('/smart-config/run', d),
  auto: (scope = 'all', routing = 'ospf', nat = false, overwriteManual = false) =>
    api.post('/smart-config/auto', { scope, routing, nat, overwrite_manual: overwriteManual }),
}

export const ManualAPI = {
  run: (d) => api.post('/manual-config/run', d),
}

export const MonitoringAPI = {
  ping: (d) => api.post('/monitoring/ping', d),
  packet: (source_device_id, target_device_id) =>
    api.post('/monitoring/packet', { source_device_id, target_device_id }),
  endpoints: () => api.get('/monitoring/endpoints'),
}

export const DashboardAPI = { get: () => api.get('/dashboard') }
export const LogAPI = { list: (params) => api.get('/logs', { params }) }

export default api
