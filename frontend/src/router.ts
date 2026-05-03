import { createRouter, createWebHistory } from 'vue-router'
import WatchLater from './views/WatchLater.vue'
import Queue from './views/Queue.vue'
import Blacklist from './views/Blacklist.vue'
import Triage from './views/Triage.vue'
import Settings from './views/Settings.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: WatchLater, name: 'watchlater', meta: { title: '稍后再看' } },
    { path: '/queue', component: Queue, name: 'queue', meta: { title: '待选视频' } },
    { path: '/filtered', redirect: { name: 'queue' } }, // legacy URL
    { path: '/blacklist', component: Blacklist, name: 'blacklist', meta: { title: '黑名单' } },
    { path: '/decide', redirect: { name: 'watchlater' } }, // legacy URL
    { path: '/triage', component: Triage, name: 'triage', meta: { title: 'AI 智选' } },
    { path: '/stats', redirect: { name: 'watchlater' } }, // legacy URL
    { path: '/settings', component: Settings, name: 'settings', meta: { title: '设置' } },
  ],
})
