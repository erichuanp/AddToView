import { createRouter, createWebHistory } from 'vue-router'
import WatchLater from './views/WatchLater.vue'
import Filtered from './views/Filtered.vue'
import Blacklist from './views/Blacklist.vue'
import Stats from './views/Stats.vue'
import Settings from './views/Settings.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: WatchLater, name: 'watchlater', meta: { title: '稍后再看' } },
    { path: '/filtered', component: Filtered, name: 'filtered', meta: { title: '已过滤' } },
    { path: '/blacklist', component: Blacklist, name: 'blacklist', meta: { title: '黑名单' } },
    { path: '/stats', component: Stats, name: 'stats', meta: { title: '统计' } },
    { path: '/settings', component: Settings, name: 'settings', meta: { title: '设置' } },
  ],
})
