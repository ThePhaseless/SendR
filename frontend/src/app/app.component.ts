import { Component } from "@angular/core";
import { HeaderComponent } from "./components/header/header.component";
import { RouterOutlet } from "@angular/router";

@Component({
  imports: [RouterOutlet, HeaderComponent],
  selector: "app-root",
  styleUrl: "./app.component.scss",
  templateUrl: "./app.component.html",
})
export class AppComponent {}
