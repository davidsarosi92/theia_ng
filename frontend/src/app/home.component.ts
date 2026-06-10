import { Component } from '@angular/core';

import { getConfig } from './theia-config';

@Component({
  selector: 'theia-home',
  standalone: true,
  template: `
    <h2>{{ title }}</h2>
    <p>Select a model from the sidebar to browse and edit records.</p>
  `,
})
export class HomeComponent {
  title = getConfig().siteTitle;
}
