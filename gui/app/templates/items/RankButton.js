'use strict';

import React, { Component } from "react";

class RankButton extends Component {
  constructor(props) {
    super(props);
    this.state = { selectedOption: "Both" };
  }

  handleOptionChange = changeEvent => {
    this.setState({
      selectedOption: changeEvent.target.value
    });
  };

  handleFormSubmit = formSubmitEvent => {
    formSubmitEvent.preventDefault();

    console.log("You have submitted:", this.state.selectedOption);
  };

  render() {
      return (
        <div className="container">
          <div className="row mt-5">
            <div className="col-sm-12">
              <form onSubmit={this.handleFormSubmit}>

                <div className="form-check">

                    <label> <br/> <b> Rank-Level </b> <br/> </label>

                    <input type="radio" name="rank" value="genus" id="genus"
                           checked={this.state.selectedOption==="genus"} onChange={this.handleOptionChange}
                           className="form-check-input" />
                    <label class="form-check-label" for="genus"> Genus-Level </label>

                </div>

                <div className="form-check">

                    <input type="radio"  name="rank" value="species" id="species"
                           checked={this.state.selectedOption==="species"} onChange={this.handleOptionChange}
                           className="form-check-input" />
                    <label class="form-check-label" for="species"> Species-Level </label>

                </div>

                <div className="form-check">

                    <input type="radio"  name="rank" value="Both" id="all_ranks"
                           checked={this.state.selectedOption==="Both"} onChange={this.handleOptionChange}
                           className="form-check-input" />
                    <label class="form-check-label" for="all_ranks"> No Rank Filter </label>

                </div>
              </form>
          </div>
        </div>
      </div>
    );
  }
}

export default RankButton;