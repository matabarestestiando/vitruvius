import {createApp} from 'vue';
import {createVuetify} from 'vuetify';
import {aliases,mdi} from 'vuetify/iconsets/mdi-svg';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import 'vuetify/styles';
import './style.css';
import App from './App.vue';
createApp(App).use(createVuetify({components,directives,icons:{defaultSet:'mdi',aliases,sets:{mdi}},theme:{defaultTheme:'dark',themes:{dark:{dark:true,colors:{background:'#10141c',surface:'#1a2130',primary:'#a8baff',secondary:'#87d7c3'}}}}})).mount('#app');
