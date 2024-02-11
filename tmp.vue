<template>
  <div class="w-full">
    <BaseModule :color="statusColor" :glow="success" :button="true"
                :status="!!show_error && !urls.length || success && urls.length && !request_refresh && !request_terminate">
      <template #default>
        <div>
          <div class="mr-5">
            Lab
            <span class="font-bold">
                        {module.lab_name || module.lab_lab}
                    </span>
            <span v-if="request_status || request_start || request_terminate" key="0" class="ml-2 text-grey">
                        <Icon class="fa-spin" :icon="[
                            'fas',
                            'sync'
                        ]"/>
                    </span>
            <div v-if="module.lab_tier > getUser.account?.tier" key="1"
                 class="font-normal mt-1 text-base text-white text-opacity-50"/>
          </div>
          <div v-if="httpUrls.length" key="0" class="w-full mt-2">
            <template>
              <div v-for="c in httpUrls" :key="c">
                \u2022
                <a class="text-green hover:underline font-normal cursor-pointer" target="_blank"
                   :href="`https://${c.host}`">
                  {c.host.split("-", -2).slice(0, -1).join(" ")}
                </a>
              </div>
            </template>
          </div>
        </div>
      </template>
      <template #button>
        <div v-if="success && urls.length && timeleft / maxtime < .1" key="0" class="flex-row flex"/>
        <Button v-if="module.lab_tier > getUser.account?.tier" key="1" color="darker" :to="{name: 'subscription'}">
          UPGRADE ACCOUNT
        </Button>
        <Button v-if="!urls.length && !show_error && !request_start && !request_status" key="2" :onClick="startLab">
          ACCESS LAB
        </Button>
        <Button v-if="show_error && !request_start" key="3" color="red" :onClick="startLab">RETRY ACCESS</Button>
        <Button v-else key="4" color="dark" :disabled="true" class="opacity-0">LOADING...</Button>
      </template>
      <template #status>
        <div v-if="show_error" key="0" class="text-red"/>
        <div v-if="success && urls.length && !request_terminate" key="1" class="text-right flex-grow">
          <Button :onClick="stopLab" :disabled="request_terminate" :color="request_terminate ? 'dark' : 'darker'"
                  class="ml-5 mt-5 sm:mt-0">
            STOP LAB
          </Button>
          <Button v-if="httpUrls.length === 1" key="0" color="green"
                  onClick="(c) => openUrl(`https://${urls[0].host}`, '_blank')" class="ml-5 mt-5 sm:mt-0">
            OPEN LAB
          </Button>
        </div>
      </template>
    </BaseModule>
  </div>
</template>
<script>
import {ref, computed} from 'vue'
import {onBeforeUnmount, tierToName, Button} from 'index.js'
import BaseModule from './BaseModule.vue' /*import {h as br, B as Bt} from "./hex_pcb.js"*/
/*Original imports, might help you find the needed variables that are  being imported*/
/*
import {d as ge, $data as x, H as Er, _ as Se, $setup as Z, b as y, e as B, h as w, i as j, l as X, w as z, f as A, C as Mt, p as J, g as Ut, J as Cn, c as de, K as _t, B as ze, k as On, v as In, m as Q, F as Ve, u as Ft, t as te, j as tn, R as An, U as vn, o as gr, O as Sr, N as be, I as Ge, y as Tr} from "./index.js"
import {h as br, B as Bt} from "./hex_pcb.js"
*/

export default {
  name: "LabModule",
  props: {
    pk: {
      type: Number,
      required: true
    },
    module: {
      type: Object,
      required: true
    },
    training_slug: {
      type: String,
      required: true
    }
  },
  setup: function (e) {
    const t = ref(false),
        n = ref(false),
        a = ref(""),
        r = ref(false),
        i = ref(false),
        s = ref(false),
        o = ref(false),
        l = ref(false),
        c = ref([]),
        _ = ref(""),
        u = ref(0),
        m = ref(0),
        E = ref(0),
        p = ref(0),
        g = ref(false),
        T = computed(() => o.value || r.value || s.value || i.value ? "yellow" : t.value ? "green" : n.value ? "red" : "green"),
        C = computed(() => c.value.filter((b) => b.protocol.startsWith("http"))),
        f = computed(() => {
          let b = E.value

          b < 0 && b = 0
          const W = Math.floor(b % 60),
              se = Math.floor(b / 60),
              pe = Math.floor(b / 60 / 60)

          return pe > 0 ? `${pe}:${se.toString().padStart(2, "0")}h` : `${se}:${W.toString().padStart(2, "0")}`
        })

    onBeforeUnmount(() => {
      N()
    })
    const N = () => {
          (clearInterval(p.value), p.value = 0, E.value = 0, g.value = false)
        },
        v = () => {
          const b = new Date().getTime(),
              W = b - m.value

          m.value = b
          const se = E.value - W / 1e3

          (E.value = se, E.value <= 0 && N())
        },
        M = () => {
          (be.start(), r.value = true, Ge.post("/api/lab/start", {
            module_pk: e.pk,
            lab_slug: e.module.lab_lab
          }).then(({
                     data: b
                   }) => {
            if ((_.value = b.server, n.value = b.error || false, t.value = !n.value, a.value = b.error ? b.msg : "", E.value = b.timeleft > 0 ? b.timeleft : 0, u.value = b.maxtime, i.value = true, be.inc(), !b.urls.length)) (be.done(), N()) else {
              E.value / u.value < .1 && q()
              let W = new Map()

              (localStorage.labs && W = new Map(JSON.parse(localStorage.labs)), W.set(e.module.lab_lab || e.pk, {
                server: _.value
              }), localStorage.labs = JSON.stringify(Array.from(W.entries())), g.value || setTimeout(() => {
                (g.value = true, P())
              }, 3e3), p.value == 0 && (m.value = new Date().getTime(), p.value = setInterval(v, 1e3)))
            }
          }).catch(O).finally(() => {
            r.value = false
          }))
        },
        O = (b) => {
          if (b.response.status == 429) (n.value = true, a.value = b.response.data.detail) else {
            if (localStorage.labs) {
              let W = new Map(JSON.parse(localStorage.labs))

              (W.delete(e.module.lab_lab || e.pk), localStorage.labs = JSON.stringify(Array.from(W.entries())))
            }
            (n.value = true, b.response.data.msg ? a.value = b.response.data.msg : b.response.data.error && a.value = b.response.data.error, t.value = false, g.value = false)
          }
        },
        P = () => {
          (i.value = true, Ge.post("/api/lab/status", {
            module_pk: e.pk,
            lab_slug: e.module.lab_lab,
            server: _.value
          }).then(({
                     data: b
                   }) => {
            (t.value = true, n.value = b.error || false, a.value = b.error ? b.msg : "", E.value = b.timeleft > 0 ? b.timeleft : 0, u.value = b.maxtime, c.value = b.urls || [], E.value == null ? g.value = false : g.value && setTimeout(() => {
              P()
            }, 3e4))
          }).catch(O).finally(() => {
            (i.value = false, r.value = false, be.done())
          }))
        },
        q = () => {
          (be.start(), o.value = true, Ge.post("/api/lab/refresh", {
            module_pk: e.pk,
            lab_slug: e.module.lab_lab,
            server: _.value
          }).then(({
                     data: b
                   }) => {
            (t.value = true, n.value = b.error || false, a.value = b.error ? b.msg : "", E.value = b.timeleft > 0 ? b.timeleft : 0, m.value = new Date().getTime(), setInterval(v, 1e3))
          }).catch((b) => {
            if (localStorage.labs) {
              let W = new Map(JSON.parse(localStorage.labs))

              (W.delete(e.module.lab_lab || e.pk), localStorage.labs = JSON.stringify(Array.from(W.entries())))
            }
            (b.response.data.msg && a.value = b.response.data.msg, b.response.data.error && a.value = b.response.data.error, n.value = true, t.value = false)
          }).finally(() => {
            (o.value = false, be.done())
          }))
        }

    if (localStorage.labs) {
      const W = new Map(JSON.parse(localStorage.labs)).get(e.module.lab_lab || e.pk)

      W && (_.value = W.server, g.value || (g.value = true, r.value = true, P()))
    }
    return {
      openUrl: function (b) {
        window.open(b, "_blank")
      },
      success: t,
      show_error: n,
      error_msg: a,
      urls: c,
      httpUrls: C,
      server: _,
      request_start: r,
      request_status: i,
      request_refresh: o,
      request_terminate: s,
      maxtime: u,
      down: l,
      statusColor: T,
      countdownStart: m,
      timeleft: E,
      progressTime: f,
      intervalStatus: g,
      intervalCountdown: p,
      startLab: M,
      stopLab: () => {
        (s.value = true, E.value = 0, Ge.post("/api/lab/stop", {
          module_pk: e.pk,
          lab_slug: e.module.lab_lab,
          server: _.value
        }).then(({
                   data: b
                 }) => {
          (n.value = b.error || false, a.value = b.error ? b.msg : "", c.value = [])
        }).catch((b) => {
          (b = true, a.value = b.response.data.msg, t.value = false)
        }).finally(() => {
          if ((t.value = false, N(), be.done(), s.value = false, localStorage.labs)) {
            let b = new Map(JSON.parse(localStorage.labs))

            (b.delete(e.module.lab_lab || e.pk), localStorage.labs = JSON.stringify(Array.from(b.entries())))
          }
        }))
      },
      tierToName
    }
  },
  computed: {
    ..._t
  },
  components: {
    Button,
    BaseModule
  }
}
</script>
